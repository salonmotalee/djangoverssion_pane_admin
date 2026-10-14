from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from operations.serializers import digits
from portal.views import IsOrganizationUser
from scheduling.models import ScheduleAssignment
from scheduling.serializers import ScheduleAssignmentSerializer
from staff.permissions import IsSupervisor, authorized_halls

from .models import AttendanceRecord, PresenceEvent
from .serializers import (
    AttendanceSelection,
    AutomaticPayload,
    CorrectionPayload,
    ManualPayload,
    PresencePayload,
)
from .services import (
    StaleAttendance,
    actor_context,
    attendance_roster,
    automatic_plan,
    calculate_status,
    can_edit,
    create_decision,
    current_students,
    events_for_roster,
    hall_for,
    make_preview_token,
    read_preview_token,
    record_presence,
    require_edit,
    session_context,
    write_decisions,
)


def session_data(session):
    return {
        "id": session.pk,
        "title": session.title,
        "start_time": session.start_time,
        "end_time": session.end_time,
    }


def account_name(account):
    return f"{account.supervisor.first_name} {account.supervisor.last_name}"


def event_data(event):
    return {
        "id": event.pk,
        "student": event.student_id,
        "student_name": f"{event.student.first_name} {event.student.last_name}",
        "identifier": event.student.identifier,
        "hall": event.hall_id,
        "hall_name": event.hall_name,
        "kind": event.kind,
        "occurred_at": event.occurred_at,
        "supervisor_name": account_name(event.actor),
        "sequence": event.sequence,
    }


def record_data(record, account, *, manager=False):
    if record is None:
        return None
    result = {
        "id": record.pk,
        "status": record.status,
        "source": record.source,
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "recorder": {"id": record.original_recorder_id, "name": account_name(record.original_recorder)},
        "early_departure": record.early_departure,
        "departed_at": record.departed_at,
        "can_edit": manager or can_edit(record, account),
        "hall": record.hall_id,
        "hall_name": record.hall_name,
        "date": record.date,
        "session": record.session_id,
        "session_title": record.session_title,
        "session_start_time": record.session_start_time,
        "session_end_time": record.session_end_time,
    }
    if manager:
        result["audit"] = [
            {
                "id": audit.pk,
                "actor_name": (
                    audit.acting_manager.portal_username
                    if audit.acting_manager_id
                    else account_name(audit.acting_supervisor)
                ),
                "original_recorder_name": account_name(audit.original_recorder),
                "previous": audit.previous,
                "new": audit.new,
                "reason": audit.reason,
                "created_at": audit.created_at,
            }
            for audit in record.audit_entries.all()
        ]
    return result


def student_data(student):
    return {
        "id": student.pk,
        "identifier": student.identifier,
        "first_name": student.first_name,
        "last_name": student.last_name,
    }


def attendance_context(organization, account, payload, *, manager=False, include_roster=True):
    hall = hall_for(organization, account, payload["hall"])
    day = payload["date"]
    sessions, session, start, end = session_context(organization, hall, day, payload.get("session"))
    response = {
        "hall": hall.pk,
        "hall_name": hall.name,
        "date": day,
        "session": session.pk if session else None,
        "sessions": [session_data(item) for item in sessions],
        "starts_at": start,
        "ends_at": end,
        "server_time": timezone.now(),
        "provisional": bool(end and timezone.now() < end),
        "students": [],
    }
    if session and include_roster:
        students, records = attendance_roster(
            organization, hall, session, day, start, end, include_audit=manager
        )
        response["students"] = [
            {
                **student_data(student),
                "record": record_data(records.get(student.pk), account, manager=manager),
            }
            for student in students
        ]
    return hall, session, start, end, response


class SupervisorAPIView(APIView):
    permission_classes = [IsSupervisor]


class SupervisorHallsView(SupervisorAPIView):
    def get(self, request, slug):
        _, account = actor_context(request, slug)
        halls = (
            authorized_halls(account)
            .annotate(active_students=Count("students", filter=Q(students__is_active=True)))
            .prefetch_related("sessions")
        )
        return Response(
            [
                {
                    "id": hall.pk,
                    "name": hall.name,
                    "active_students": hall.active_students,
                    "sessions": [
                        session_data(session) for session in hall.sessions.all() if session.is_active
                    ],
                }
                for hall in halls
            ]
        )


class SupervisorStudentsView(SupervisorAPIView):
    def get(self, request, slug):
        organization, account = actor_context(request, slug)
        students = current_students(organization, account)
        hall_id = request.query_params.get("hall")
        if hall_id:
            selection = AttendanceSelection(data={"hall": hall_id, "date": timezone.localdate()})
            selection.is_valid(raise_exception=True)
            hall = hall_for(organization, account, selection.validated_data["hall"])
            students = students.filter(hall=hall)
        search = digits(request.query_params.get("search", "").strip())
        if search:
            terms = search.split()
            for term in terms:
                students = students.filter(
                    Q(first_name__icontains=term)
                    | Q(last_name__icontains=term)
                    | Q(identifier__icontains=term)
                )
        inside = request.query_params.get("inside")
        if inside is not None:
            if inside not in {"true", "false"}:
                raise ValidationError({"inside": "فیلتر حضور باید true یا false باشد."})
            students = (
                students.filter(last_kind="entry")
                if inside == "true"
                else students.exclude(last_kind="entry")
            )
        students = students.order_by("last_name", "first_name", "pk")
        pager = StandardPagination()
        page = pager.paginate_queryset(students, request)
        return pager.get_paginated_response(
            [
                {
                    **student_data(student),
                    "hall": student.hall_id,
                    "hall_name": student.hall.name,
                    "desk_number": student.desk_number,
                    "inside": student.last_kind == "entry",
                    "last_event_at": student.last_event_at,
                    "presence_hall": student.presence_hall_id if student.last_kind == "entry" else None,
                }
                for student in page
            ]
        )


class PresenceView(SupervisorAPIView):
    def get(self, request, slug):
        organization, account = actor_context(request, slug)
        events = PresenceEvent.objects.filter(
            organization=organization, hall__in=authorized_halls(account)
        ).select_related("student", "actor__supervisor")
        hall_id = request.query_params.get("hall")
        if hall_id:
            selection = AttendanceSelection(data={"hall": hall_id, "date": timezone.localdate()})
            selection.is_valid(raise_exception=True)
            events = events.filter(hall=hall_for(organization, account, selection.validated_data["hall"]))
        student_id = request.query_params.get("student")
        if student_id:
            try:
                student_id = int(student_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"student": "شناسهٔ دانش‌آموز معتبر نیست."}) from exc
            events = events.filter(student_id=student_id)
        pager = StandardPagination()
        ordering = request.query_params.get("ordering", "occurred_at")
        if ordering not in {"occurred_at", "-occurred_at"}:
            raise ValidationError({"ordering": "مرتب‌سازی معتبر نیست."})
        page = pager.paginate_queryset(
            events.order_by(ordering, "-pk" if ordering.startswith("-") else "pk"), request
        )
        return pager.get_paginated_response([event_data(event) for event in page])

    @transaction.atomic
    def post(self, request, slug):
        payload = PresencePayload(data=request.data)
        payload.is_valid(raise_exception=True)
        organization, account = actor_context(request, slug, lock=True)
        event = record_presence(
            organization,
            account,
            **{"student_id": payload.validated_data["student"], "kind": payload.validated_data["kind"]},
        )
        return Response(event_data(event), status=201)


class SupervisorAttendanceView(SupervisorAPIView):
    def get(self, request, slug):
        payload = AttendanceSelection(data=request.query_params)
        payload.is_valid(raise_exception=True)
        organization, account = actor_context(request, slug)
        return Response(attendance_context(organization, account, payload.validated_data)[-1])


class ManualAttendanceView(SupervisorAPIView):
    @transaction.atomic
    def post(self, request, slug):
        payload = ManualPayload(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        organization, account = actor_context(request, slug, lock=True)
        now = timezone.now()
        if data["date"] > timezone.localdate(now):
            raise ValidationError({"date": "ثبت حضور و غیاب برای تاریخ آینده مجاز نیست."})
        hall, session, start, end, _ = attendance_context(organization, account, data, include_roster=False)
        students, records = attendance_roster(organization, hall, session, data["date"], start, end)
        by_id = {student.pk: student for student in students}
        events = events_for_roster(organization, list(by_id), start, end)
        # Validate every target before making any change.
        for item in data["records"]:
            if item["student"] not in by_id:
                raise PermissionDenied("دانش‌آموز به فهرست این سالن تعلق ندارد.")
            record = records.get(item["student"])
            if record:
                require_edit(record, account, item.get("revision"), now)
            elif item.get("revision") is not None:
                raise StaleAttendance()
        changes = []
        for item in data["records"]:
            record = records.get(item["student"])
            decision = calculate_status(events[item["student"]], hall.pk, start, end)
            decision["status"] = item["status"]
            if record:
                changes.append((record, decision))
            else:
                create_decision(
                    organization,
                    account,
                    hall,
                    session,
                    data["date"],
                    start,
                    end,
                    by_id[item["student"]],
                    decision,
                    "manual",
                )
        write_decisions(changes, account=account, source="manual", now=now)
        return Response({"updated": len(data["records"])})


class AutomaticPreviewView(SupervisorAPIView):
    def post(self, request, slug):
        payload = AttendanceSelection(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if not data.get("session"):
            raise ValidationError({"session": "پارت را انتخاب کنید."})
        organization, account = actor_context(request, slug)
        hall, session, start, end, response = attendance_context(
            organization, account, data, include_roster=False
        )
        if timezone.now() < start:
            raise ValidationError({"date": "پیش‌نمایش خودکار پس از شروع پارت در دسترس است."})
        students, records, decisions, digest = automatic_plan(
            organization, account, hall, session, data["date"], start, end
        )
        response["students"] = [
            {
                **student_data(student),
                "record": record_data(records.get(student.pk), account),
                "calculated_status": decisions[student.pk]["status"],
                "early_departure": decisions[student.pk]["early_departure"],
                "departed_at": decisions[student.pk]["departed_at"],
                "selectable": student.pk not in records
                or (records[student.pk].source == "automatic" and can_edit(records[student.pk], account)),
            }
            for student in students
        ]
        response["preview_token"] = make_preview_token(
            organization, account, hall, session, data["date"], digest, response["provisional"]
        )
        return Response(response)


class AutomaticFinalizeView(SupervisorAPIView):
    @transaction.atomic
    def post(self, request, slug):
        payload = AutomaticPayload(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        preview = read_preview_token(data["preview_token"])
        organization, account = actor_context(request, slug, lock=True)
        if preview["org"] != organization.pk or preview["actor"] != account.pk:
            raise PermissionDenied("پیش‌نمایش متعلق به این مراقب و مجموعه نیست.")
        selection = {
            "hall": preview["hall"],
            "session": preview["session"],
            "date": date.fromisoformat(preview["date"]),
        }
        hall, session, start, end, _ = attendance_context(
            organization, account, selection, include_roster=False
        )
        now = timezone.now()
        if preview["provisional"] or now < end:
            raise ValidationError(
                {"preview_token": "پیش‌نمایش موقت قابل ثبت نهایی نیست؛ پس از پایان پارت دوباره محاسبه کنید."}
            )
        students, records, decisions, digest = automatic_plan(
            organization, account, hall, session, selection["date"], start, end
        )
        if digest != preview["digest"]:
            raise StaleAttendance()
        by_id = {student.pk: student for student in students}
        for student_id in data["students"]:
            if student_id not in by_id:
                raise PermissionDenied("دانش‌آموز به فهرست پیش‌نمایش تعلق ندارد.")
            record = records.get(student_id)
            if record:
                if record.source == "manual":
                    raise PermissionDenied("حضور و غیاب دستی با محاسبهٔ خودکار بازنویسی نمی‌شود.")
                require_edit(record, account, record.revision, now)
        changes = []
        for student_id in data["students"]:
            record = records.get(student_id)
            decision = decisions[student_id]
            if record:
                changes.append((record, decision))
            else:
                create_decision(
                    organization,
                    account,
                    hall,
                    session,
                    selection["date"],
                    start,
                    end,
                    by_id[student_id],
                    decision,
                    "automatic",
                )
        write_decisions(changes, account=account, now=now)
        return Response({"updated": len(data["students"])})


class ManagerAttendanceView(APIView):
    permission_classes = [IsOrganizationUser]

    def get(self, request, slug):
        payload = AttendanceSelection(data=request.query_params)
        payload.is_valid(raise_exception=True)
        organization, _ = actor_context(request, slug, manager=True)
        return Response(attendance_context(organization, None, payload.validated_data, manager=True)[-1])


class ManagerCorrectionView(APIView):
    permission_classes = [IsOrganizationUser]

    @transaction.atomic
    def post(self, request, slug):
        payload = CorrectionPayload(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        organization, _ = actor_context(request, slug, manager=True, lock=True)
        records = {
            record.pk: record
            for record in AttendanceRecord.objects.select_for_update()
            .filter(organization=organization, pk__in=[item["id"] for item in data["records"]])
            .select_related("student", "hall", "session", "original_recorder")
        }
        for item in data["records"]:
            record = records.get(item["id"])
            if not record:
                raise PermissionDenied("رکورد به این مجموعه تعلق ندارد.")
            if record.revision != item["revision"]:
                raise StaleAttendance()
        write_decisions(
            [(records[item["id"]], {"status": item["status"]}) for item in data["records"]],
            manager=request.user,
            reason=data["reason"],
            source="manual",
        )
        return Response({"updated": len(data["records"])})


class SupervisorDashboardView(SupervisorAPIView):
    def get(self, request, slug):
        organization, account = actor_context(request, slug)
        halls = list(
            authorized_halls(account)
            .annotate(active_students=Count("students", filter=Q(students__is_active=True)))
            .prefetch_related("sessions")
        )
        today = timezone.localdate()
        students = current_students(organization, account)
        completed = AttendanceRecord.objects.filter(
            organization=organization, hall__in=halls, date=today
        ).count()
        expected = sum(hall.active_students * sum(s.is_active for s in hall.sessions.all()) for hall in halls)
        response = {
            "organization": {
                "name": organization.name,
                "slug": organization.slug,
                "subscription_status": organization.status,
            },
            "server_time": timezone.now(),
            "today": today,
            "halls": [
                {
                    "id": hall.pk,
                    "name": hall.name,
                    "active_students": hall.active_students,
                    "sessions": [
                        session_data(session) for session in hall.sessions.all() if session.is_active
                    ],
                }
                for hall in halls
            ],
            "student_count": students.count(),
            "inside_count": students.filter(last_kind="entry").count(),
            "today_attendance": {"completed": completed, "pending": max(0, expected - completed)},
            "today_shifts": [],
            "upcoming_shifts": [],
        }
        shifts = (
            ScheduleAssignment.objects.filter(
                organization=organization,
                supervisor_id=account.supervisor_id,
                hall__in=halls,
                date__gte=today,
            )
            .select_related("hall", "supervisor", "shift")
            .order_by("date", "start_time", "pk")
        )
        response["today_shifts"] = ScheduleAssignmentSerializer(shifts.filter(date=today), many=True).data
        response["upcoming_shifts"] = ScheduleAssignmentSerializer(
            shifts.filter(date__gt=today)[:12], many=True
        ).data
        return Response(response)
