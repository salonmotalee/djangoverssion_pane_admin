"""Serialized write services. A Customer lock also serializes student transfers/grant changes."""

import hashlib
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core import signing
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from core.models import Customer, User
from operations.models import Hall, Student, StudySession
from portal.views import owned_organization
from staff.permissions import authorized_halls, current_supervisor

from .models import AttendanceAudit, AttendanceRecord, PresenceEvent

TEHRAN = ZoneInfo("Asia/Tehran")
PREVIEW_SALT = "damavand.attendance.preview.v1"


class StaleAttendance(APIException):
    status_code = 409
    default_detail = "اطلاعات تغییر کرده است؛ پیش‌نمایش یا فهرست را تازه کنید."


def actor_context(request, slug, *, manager=False, lock=False):
    actor = owned_organization(request, slug) if manager else current_supervisor(request, slug)
    organization = actor if manager else actor.organization
    if lock:
        Customer.objects.select_for_update().get(pk=organization.pk)
        if manager:
            manager_user = User.objects.filter(pk=request.user.pk).first()
            if (
                manager_user is None
                or not manager_user.is_active
                or manager_user.role != User.Role.TENANT
                or manager_user.organization_id != organization.pk
                or manager_user.get_session_auth_hash() != request.user.get_session_auth_hash()
            ):
                raise PermissionDenied("دسترسی مدیر تغییر کرده است؛ دوباره وارد شوید.")
        actor = owned_organization(request, slug) if manager else current_supervisor(request, slug)
        organization = actor if manager else actor.organization
    return organization, None if manager else actor


def hall_for(organization, account, hall_id):
    queryset = Hall.objects.filter(organization=organization)
    if account is not None:
        queryset = authorized_halls(account)
    return get_object_or_404(queryset, pk=hall_id)


def session_context(organization, hall, day, session_id):
    sessions = (
        StudySession.objects.filter(organization=organization)
        .filter(
            Q(is_active=True, halls=hall) | Q(attendance_records__hall=hall, attendance_records__date=day)
        )
        .distinct()
        .order_by("start_time", "pk")
    )
    session = get_object_or_404(sessions, pk=session_id) if session_id is not None else None
    if not session:
        return sessions, None, None, None
    snapshot = AttendanceRecord.objects.filter(
        organization=organization, hall=hall, session=session, date=day
    ).first()
    start_time = snapshot.session_start_time if snapshot else session.start_time
    end_time = snapshot.session_end_time if snapshot else session.end_time
    return (
        sessions,
        session,
        datetime.combine(day, start_time, tzinfo=TEHRAN),
        datetime.combine(day, end_time, tzinfo=TEHRAN),
    )


def can_edit(record, account, now=None):
    return bool(
        account
        and record.original_recorder_id == account.pk
        and (now or timezone.now()) <= record.created_at + timedelta(hours=48)
    )


def require_edit(record, account, revision, now):
    if not can_edit(record, account, now):
        raise PermissionDenied("فقط مراقب ثبت‌کننده تا ۴۸ ساعت پس از ثبت اولیه اجازهٔ ویرایش دارد.")
    if revision != record.revision:
        raise StaleAttendance()


def decision_snapshot(record):
    return {
        "status": record.status,
        "source": record.source,
        "early_departure": record.early_departure,
        "departed_at": record.departed_at.isoformat() if record.departed_at else None,
        "revision": record.revision,
    }


def write_decisions(changes, *, account=None, manager=None, reason="", source=None, now=None):
    """Persist already authorized/revision-checked changes in bounded batches.

    Callers hold the organization lock. Only mutable decision fields are written;
    ownership, hall/session snapshots and initial creation timestamps stay intact.
    Every changed row receives a corresponding audit row in the same transaction.
    """
    records, audits = [], []
    timestamp = now or timezone.now()
    for record, decision in changes:
        before = decision_snapshot(record)
        record.status = decision["status"]
        if source is not None:
            record.source = source
        if "early_departure" in decision:
            record.early_departure = decision["early_departure"]
            record.departed_at = decision["departed_at"]
        record.revision += 1
        record.updated_at = timestamp
        records.append(record)
        audits.append(
            AttendanceAudit(
                record=record,
                acting_manager=manager,
                acting_supervisor=account,
                original_recorder_id=record.original_recorder_id,
                previous=before,
                new=decision_snapshot(record),
                reason=reason,
                created_at=timestamp,
            )
        )
    if records:
        AttendanceRecord.objects.bulk_update(
            records,
            ["status", "source", "early_departure", "departed_at", "revision", "updated_at"],
            batch_size=100,
        )
        AttendanceAudit.objects.bulk_create(audits, batch_size=200)


def record_presence(organization, account, student_id, kind):
    student = get_object_or_404(
        Student.objects.select_for_update().filter(
            organization=organization, is_active=True, hall__in=authorized_halls(account)
        ),
        pk=student_id,
    )
    last = (
        PresenceEvent.objects.filter(organization=organization, student=student).order_by("-sequence").first()
    )
    if (last and last.kind == kind) or (last is None and kind == PresenceEvent.Kind.EXIT):
        raise ValidationError({"kind": "ورود یا خروج متوالی تکراری مجاز نیست."})
    # A transfer never rewrites history: the new hall supervisor can close an
    # inherited open entry, whose exit keeps the entry's original hall snapshot.
    hall = last.hall if kind == PresenceEvent.Kind.EXIT else student.hall
    return PresenceEvent.objects.create(
        organization=organization,
        student=student,
        hall=hall,
        hall_name=last.hall_name if kind == PresenceEvent.Kind.EXIT else hall.name,
        actor=account,
        kind=kind,
        sequence=(last.sequence + 1) if last else 1,
        occurred_at=timezone.now(),
    )


def current_students(organization, account):
    latest = PresenceEvent.objects.filter(student=OuterRef("pk"), organization=organization).order_by(
        "-sequence"
    )
    return (
        Student.objects.filter(organization=organization, is_active=True, hall__in=authorized_halls(account))
        .select_related("hall")
        .annotate(
            last_kind=Subquery(latest.values("kind")[:1]),
            last_event_at=Subquery(latest.values("occurred_at")[:1]),
            presence_hall_id=Subquery(latest.values("hall_id")[:1]),
        )
    )


def attendance_roster(organization, hall, session, day, start, end, *, include_audit=False):
    records = AttendanceRecord.objects.filter(
        organization=organization, hall=hall, session=session, date=day
    ).select_related("original_recorder__supervisor", "student", "hall", "session")
    if include_audit:
        records = records.prefetch_related(
            "audit_entries__acting_manager",
            "audit_entries__acting_supervisor__supervisor",
            "audit_entries__original_recorder__supervisor",
        )
    record_map = {record.student_id: record for record in records}
    # Historical entrants remain addressable for attendance after a transfer.
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=TEHRAN)
    day_end = midnight + timedelta(days=1)
    latest_start = PresenceEvent.objects.filter(
        organization=organization, student=OuterRef("pk"), occurred_at__lte=start
    ).order_by("-occurred_at", "-sequence")
    historical = (
        Student.objects.filter(organization=organization)
        .annotate(
            start_kind=Subquery(latest_start.values("kind")[:1]),
            start_hall=Subquery(latest_start.values("hall_id")[:1]),
        )
        .filter(
            Q(start_kind="entry", start_hall=hall.pk)
            | Q(
                presence_events__hall=hall,
                presence_events__occurred_at__gte=midnight,
                presence_events__occurred_at__lt=day_end,
            )
        )
        .values_list("pk", flat=True)
    )
    students = list(
        Student.objects.filter(organization=organization)
        .filter(Q(is_active=True, hall=hall) | Q(pk__in=record_map) | Q(pk__in=historical))
        .distinct()
        .order_by("last_name", "first_name", "pk")
    )
    return students, record_map


def calculate_status(events, hall_id, start, end):
    """Use half-open presence intervals; a final closed interval flags departure.

    Returning before the end clears an earlier departure. Leaving exactly at the
    end is not early. An entry/exit at the start with no duration is not presence.
    """
    entry = None
    intervals = []
    for event in events:
        if event.kind == PresenceEvent.Kind.ENTRY:
            entry = event
        elif entry is not None:
            if (
                entry.hall_id == hall_id
                and entry.occurred_at < end
                and event.occurred_at > start
                and event.occurred_at > entry.occurred_at
            ):
                intervals.append((entry.occurred_at, event.occurred_at))
            entry = None
    if entry is not None and entry.hall_id == hall_id and entry.occurred_at < end:
        intervals.append((entry.occurred_at, None))
    overlaps = [(begin, finish) for begin, finish in intervals if finish is None or finish > start]
    if not overlaps:
        return {"status": "absent", "early_departure": False, "departed_at": None}
    status = "present" if overlaps[0][0] <= start else "late"
    departure = overlaps[-1][1]
    early = departure is not None and departure < end
    return {"status": status, "early_departure": early, "departed_at": departure if early else None}


def events_for_roster(organization, student_ids, start, end):
    # A single prior event represents whether the student was already inside.
    prior = (
        PresenceEvent.objects.filter(
            organization=organization, student=OuterRef("student_id"), occurred_at__lte=start
        )
        .order_by("-occurred_at", "-sequence")
        .values("pk")[:1]
    )
    rows = (
        PresenceEvent.objects.filter(
            organization=organization,
            student_id__in=student_ids,
        )
        .filter(Q(occurred_at__gt=start, occurred_at__lte=end) | Q(pk=Subquery(prior)))
        .order_by("occurred_at", "sequence", "pk")
    )
    grouped = {student_id: [] for student_id in student_ids}
    for event in rows:
        grouped[event.student_id].append(event)
    return grouped


def automatic_plan(organization, account, hall, session, day, start, end):
    students, records = attendance_roster(organization, hall, session, day, start, end)
    events = events_for_roster(organization, [student.pk for student in students], start, end)
    decisions = {
        student.pk: calculate_status(events[student.pk], hall.pk, start, end) for student in students
    }
    fingerprint = {
        "org": organization.pk,
        "actor": account.pk,
        "hall": [hall.pk, hall.name, hall.is_active],
        "grants": list(authorized_halls(account).values_list("pk", flat=True)),
        "session": [
            session.pk,
            session.title,
            str(session.start_time),
            str(session.end_time),
            session.is_active,
        ],
        "interval": [start.isoformat(), end.isoformat()],
        "students": [[s.pk, s.hall_id, s.is_active] for s in students],
        "records": [[r.pk, r.revision, r.source, r.original_recorder_id] for r in records.values()],
        "events": [
            [e.pk, e.kind, e.hall_id, e.occurred_at.isoformat()] for group in events.values() for e in group
        ],
    }
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    return students, records, decisions, digest


def make_preview_token(organization, account, hall, session, day, digest, provisional):
    return signing.dumps(
        {
            "org": organization.pk,
            "actor": account.pk,
            "hall": hall.pk,
            "session": session.pk,
            "date": day.isoformat(),
            "digest": digest,
            "provisional": provisional,
        },
        salt=PREVIEW_SALT,
        compress=True,
    )


def read_preview_token(token):
    try:
        return signing.loads(token, salt=PREVIEW_SALT, max_age=600)
    except signing.BadSignature as exc:
        raise StaleAttendance("پیش‌نمایش منقضی یا نامعتبر است؛ دوباره محاسبه کنید.") from exc


def create_decision(organization, account, hall, session, day, start, end, student, decision, source):
    return AttendanceRecord.objects.create(
        organization=organization,
        student=student,
        hall=hall,
        session=session,
        date=day,
        status=decision["status"],
        source=source,
        original_recorder=account,
        hall_name=hall.name,
        session_title=session.title,
        session_start_time=start.timetz().replace(tzinfo=None),
        session_end_time=end.timetz().replace(tzinfo=None),
        early_departure=decision.get("early_departure", False),
        departed_at=decision.get("departed_at"),
    )
