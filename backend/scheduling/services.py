"""Signed, optimistic previews followed by locked, independently validated writes."""

import hashlib
import json
from collections import defaultdict
from datetime import timedelta

import jdatetime
from django.core import signing
from django.db import transaction
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from core.models import Customer, User
from operations.models import Hall, Supervisor, SupervisorHall

from .models import ScheduleAssignment, ScheduleAudit, WorkShift
from .serializers import ScheduleAssignmentSerializer

PREVIEW_SALT = "damavand.schedule.preview.v1"
PREVIEW_AGE = 15 * 60


class StalePreview(APIException):
    status_code = 409
    default_detail = "برنامه یا دسترسی‌ها تغییر کرده است؛ پیش‌نمایش تازه بگیرید."
    default_code = "stale_preview"


def validate_live_manager(organization, actor):
    if not User.objects.filter(
        pk=actor.pk,
        role=User.Role.TENANT,
        organization=organization,
        is_active=True,
        password=actor.password,
        portal_session_version=actor.portal_session_version,
    ).exists():
        raise PermissionDenied("نشست مدیر دیگر معتبر نیست؛ دوباره وارد شوید.")


def assignment_query(organization):
    return ScheduleAssignment.objects.filter(organization=organization).select_related(
        "hall", "supervisor", "shift"
    )


def serialized_assignment(assignment):
    return dict(ScheduleAssignmentSerializer(assignment).data)


def revision(organization, dates):
    """Scope history to proposal dates; include every mutable scheduling prerequisite."""
    state = {
        "assignments": list(
            ScheduleAssignment.objects.filter(organization=organization, date__in=dates)
            .order_by("pk")
            .values(
                "id",
                "date",
                "hall_id",
                "shift_id",
                "supervisor_id",
                "start_time",
                "end_time",
                "shift_name",
                "conflict_override",
            )
        ),
        "shifts": list(
            WorkShift.objects.filter(organization=organization)
            .order_by("pk")
            .values("id", "name", "start_time", "end_time", "is_active", "updated_at")
        ),
        "halls": list(
            Hall.objects.filter(organization=organization).order_by("pk").values("id", "is_active")
        ),
        "supervisors": list(
            Supervisor.objects.filter(organization=organization)
            .order_by("pk")
            .values("id", "is_active", "archived_at")
        ),
        "grants": list(
            SupervisorHall.objects.filter(supervisor__organization=organization)
            .order_by("pk")
            .values_list("supervisor_id", "hall_id")
        ),
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def row_key(row):
    return (str(row["date"]), row["hall"], row["shift"], row["supervisor"])


def slot_key(row):
    return (str(row["date"]), row["hall"], row["shift"])


def resolve_rows(organization, specs):
    halls = {
        obj.pk: obj
        for obj in Hall.objects.filter(organization=organization, pk__in={r["hall"] for r in specs})
    }
    shifts = {
        obj.pk: obj
        for obj in WorkShift.objects.filter(organization=organization, pk__in={r["shift"] for r in specs})
    }
    supervisors = {
        obj.pk: obj
        for obj in Supervisor.objects.filter(
            organization=organization, pk__in={r["supervisor"] for r in specs}
        )
    }
    grants = set(
        SupervisorHall.objects.filter(supervisor_id__in=supervisors, hall_id__in=halls).values_list(
            "supervisor_id", "hall_id"
        )
    )
    rows = []
    for index, spec in enumerate(specs):
        hall, shift, supervisor = (
            halls.get(spec["hall"]),
            shifts.get(spec["shift"]),
            supervisors.get(spec["supervisor"]),
        )
        if any(obj is None for obj in (hall, shift, supervisor)):
            raise ValidationError({"assignments": "سالن، شیفت یا مراقب انتخاب‌شده در این مجموعه یافت نشد."})
        unavailable = (
            not hall.is_active
            or not shift.is_active
            or not supervisor.is_active
            or supervisor.archived_at is not None
            or (supervisor.pk, hall.pk) not in grants
        )
        rows.append(
            {
                "index": index,
                "date": str(spec["date"]),
                "hall": hall.pk,
                "hall_name": hall.name,
                "shift": shift.pk,
                "shift_name": shift.name,
                "supervisor": supervisor.pk,
                "supervisor_name": f"{supervisor.first_name} {supervisor.last_name}",
                "start_time": shift.start_time.isoformat(),
                "end_time": shift.end_time.isoformat(),
                "error": "مراقب، سالن یا شیفت غیرفعال است، یا مراقب به این سالن دسترسی ندارد."
                if unavailable
                else "",
            }
        )
    return rows


def overlaps(left, right):
    return left["start_time"] < right["end_time"] and right["start_time"] < left["end_time"]


def conflict_key(conflict):
    return (
        tuple(sorted((tuple(conflict["left_key"]), tuple(conflict["right_key"])))),
        conflict["start_time"],
        conflict["end_time"],
    )


def detect_conflicts(proposed, existing, *, existing_only=False):
    """Intervals are half-open; adjacent shifts never conflict, across halls do."""
    groups = defaultdict(list)
    for row in existing:
        groups[(str(row["date"]), row["supervisor"])].append(
            {**row, "ref": f"existing-{row['id']}", "proposed": False}
        )
    for row in proposed:
        groups[(str(row["date"]), row["supervisor"])].append(
            {**row, "ref": f"row-{row['index']}", "proposed": True}
        )
    result = []
    seen = set()
    for (date, supervisor), group in groups.items():
        group.sort(key=lambda r: (r["start_time"], r["end_time"], r["ref"]))
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if right["start_time"] >= left["end_time"]:
                    break
                if not existing_only and not (left["proposed"] or right["proposed"]):
                    continue
                # A proposed replacement and its own persisted row are alternatives,
                # never two distinct shifts competing for the same supervisor.
                if row_key(left) == row_key(right):
                    continue
                if overlaps(left, right):
                    conflict = {
                        "left": left["ref"],
                        "right": right["ref"],
                        "supervisor": supervisor,
                        "supervisor_name": left["supervisor_name"],
                        "date": date,
                        "start_time": max(left["start_time"], right["start_time"]),
                        "end_time": min(left["end_time"], right["end_time"]),
                        "left_hall": left["hall_name"],
                        "right_hall": right["hall_name"],
                        "left_shift": left["shift_name"],
                        "right_shift": right["shift_name"],
                        "left_key": list(row_key(left)),
                        "right_key": list(row_key(right)),
                    }
                    key = conflict_key(conflict)
                    if key not in seen:
                        result.append(conflict)
                        seen.add(key)
    return result


def build_preview(organization, actor, specs, remove_ids=None, metadata=None):
    validate_live_manager(organization, actor)
    remove_ids, metadata = list(remove_ids or []), metadata or {}
    if len(set(remove_ids)) != len(remove_ids):
        raise ValidationError({"remove_ids": "شناسهٔ حذف تکراری است."})
    removals = list(assignment_query(organization).filter(pk__in=remove_ids))
    if len(removals) != len(remove_ids):
        raise ValidationError({"remove_ids": "برنامهٔ انتخاب‌شده در این مجموعه یافت نشد."})
    dates = {str(row["date"]) for row in specs} | {str(row.date) for row in removals}
    dates.update(metadata.get("source_dates", []))
    existing = [serialized_assignment(obj) for obj in assignment_query(organization).filter(date__in=dates)]
    rows = resolve_rows(organization, specs)
    slots = defaultdict(list)
    by_key = {}
    for item in existing:
        if item["id"] not in remove_ids:
            slots[slot_key(item)].append(item)
            by_key[row_key(item)] = item
    seen = set()
    for row in rows:
        key = row_key(row)
        match = by_key.get(key)
        status = "invalid" if row["error"] else "duplicate" if key in seen else "existing" if match else "new"
        row.update(
            {
                "status": status,
                "existing_id": match["id"] if match else None,
                "existing_ids": [item["id"] for item in slots[slot_key(row)]],
                "existing_assignments": slots[slot_key(row)],
                "default_action": "skip"
                if status in {"duplicate", "invalid"}
                else "preserve"
                if match
                else "add",
            }
        )
        source = metadata.get("source_times", {}).get(str(row["index"]))
        if source:
            row.update(
                {
                    "source_start_time": source[0],
                    "source_end_time": source[1],
                    "times_changed": source != [row["start_time"], row["end_time"]],
                }
            )
        seen.add(key)
    # Show every possible selected add/replace conflict, including an existing
    # exact row refreshed to new shift times and optional removals left unchecked.
    # Saving later requires acknowledgement only for conflicts that actually survive.
    proposed = [r for r in rows if not r["error"]]
    conflicts = detect_conflicts(proposed, existing)
    removed_keys = {row_key(row) for row in existing if row["id"] in remove_ids}
    for conflict in conflicts:
        conflict["resolved_by_removal"] = (
            tuple(conflict["left_key"]) in removed_keys or tuple(conflict["right_key"]) in removed_keys
        )
    for row in rows:
        row["conflicts"] = [
            c for c in conflicts if row_key(row) in {tuple(c["left_key"]), tuple(c["right_key"])}
        ]
    current_revision = revision(organization, dates)
    payload = {
        "organization": organization.pk,
        "actor": actor.pk,
        "revision": current_revision,
        "specs": [{**r, "date": str(r["date"])} for r in specs],
        "remove_ids": remove_ids,
        "dates": sorted(dates),
        "metadata": metadata,
    }
    token = signing.dumps(payload, salt=PREVIEW_SALT, compress=True)
    return {
        "token": token,
        "revision": current_revision,
        "rows": rows,
        "removals": [serialized_assignment(row) for row in removals],
        "conflicts": conflicts,
        "summary": {
            "add": sum(r["status"] == "new" for r in rows),
            "existing": sum(r["status"] == "existing" for r in rows),
            "duplicate": sum(r["status"] == "duplicate" for r in rows),
            "invalid": sum(r["status"] == "invalid" for r in rows),
            "conflicts": len(conflicts),
            "remove": len(removals),
        },
        "metadata": {k: v for k, v in metadata.items() if k not in {"source_times", "source_dates"}},
    }


@transaction.atomic
def apply_preview(organization, actor, data):
    organization = Customer.objects.select_for_update().get(pk=organization.pk)
    if organization.deleted_at is not None:
        raise ValidationError("این مجموعه بایگانی شده است.")
    validate_live_manager(organization, actor)
    try:
        payload = signing.loads(data["token"], salt=PREVIEW_SALT, max_age=PREVIEW_AGE)
    except signing.BadSignature as exc:
        raise StalePreview("پیش‌نمایش نامعتبر یا منقضی است؛ دوباره پیش‌نمایش بگیرید.") from exc
    if payload["organization"] != organization.pk or payload["actor"] != actor.pk:
        raise ValidationError({"token": "این پیش‌نمایش متعلق به نشست و مجموعهٔ جاری نیست."})
    if payload["revision"] != revision(organization, payload["dates"]):
        raise StalePreview()
    preview = build_preview(organization, actor, payload["specs"], payload["remove_ids"], payload["metadata"])
    rows = preview["rows"]
    indices = [item["index"] for item in data["actions"]]
    if len(indices) != len(set(indices)) or any(index >= len(rows) for index in indices):
        raise ValidationError({"actions": "شمارهٔ ردیف نامعتبر یا تکراری است."})
    removes = set(data["remove_ids"])
    if len(removes) != len(data["remove_ids"]) or not removes <= set(payload["remove_ids"]):
        raise ValidationError({"remove_ids": "فقط حذف‌های نمایش‌داده‌شده در پیش‌نمایش مجازند."})
    selected = []
    preserved = 0
    preserved_ids = set()
    for selection in data["actions"]:
        row = rows[selection["index"]]
        action = selection["action"]
        replacements = set(selection["replace_ids"])
        if action != "replace" and replacements:
            raise ValidationError({"actions": "شناسهٔ جایگزینی فقط همراه با عمل جایگزینی مجاز است."})
        if action == "skip":
            continue
        if action == "preserve":
            if row["existing_id"] is None:
                raise ValidationError(
                    {"actions": "ردیف جدید قابل حفظ نیست؛ افزودن یا ردکردن را انتخاب کنید."}
                )
            preserved += 1
            preserved_ids.add(row["existing_id"])
            continue
        if row["error"]:
            raise ValidationError({"actions": row["error"]})
        if action == "replace":
            if not replacements or not replacements <= set(row["existing_ids"]):
                raise ValidationError(
                    {"actions": "برنامه‌های مشخص‌شده برای جایگزینی باید از همین ردیف پیش‌نمایش باشند."}
                )
            removes.update(replacements)
        selected.append(row)
    if preserved_ids & removes:
        raise ValidationError(
            {"actions": "یک برنامه هم‌زمان برای حفظ و حذف انتخاب شده است؛ انتخاب‌ها را اصلاح کنید."}
        )
    if len({row_key(row) for row in selected}) != len(selected):
        raise ValidationError({"actions": "افزودن تخصیص تکراری مجاز نیست."})
    existing = [
        serialized_assignment(obj) for obj in assignment_query(organization).filter(date__in=payload["dates"])
    ]
    retained = [row for row in existing if row["id"] not in removes]
    retained_keys = {row_key(row) for row in retained}
    if any(row_key(row) in retained_keys for row in selected):
        raise ValidationError({"actions": "تخصیص موجود را حفظ کنید یا صریحاً برای جایگزینی انتخاب کنید."})
    conflicts = detect_conflicts(selected, retained)
    if not {conflict_key(c) for c in conflicts} <= {conflict_key(c) for c in preview["conflicts"]}:
        raise StalePreview("تداخل تازه‌ای شناسایی شد؛ انتخاب‌ها را با پیش‌نمایش جدید بررسی کنید.")
    reason = data["override_reason"].strip()
    if conflicts and (not data["confirm_conflicts"] or not reason):
        raise ValidationError(
            {"conflicts": conflicts, "detail": "تداخل شیفت‌ها نیاز به تأیید صریح و دلیل کوتاه دارد."}
        )
    conflict_refs = {ref for c in conflicts for ref in (c["left"], c["right"]) if ref.startswith("row-")}
    records = [
        ScheduleAssignment(
            organization=organization,
            date=row["date"],
            hall_id=row["hall"],
            shift_id=row["shift"],
            supervisor_id=row["supervisor"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            shift_name=row["shift_name"],
            created_by=actor,
            conflict_override=f"row-{row['index']}" in conflict_refs,
            override_reason=reason if f"row-{row['index']}" in conflict_refs else "",
        )
        for row in selected
    ]
    removed = [row for row in existing if row["id"] in removes]
    if removes:
        ScheduleAssignment.objects.filter(organization=organization, pk__in=removes).delete()
    ScheduleAssignment.objects.bulk_create(records, batch_size=500)
    if records or removed:
        ScheduleAudit.objects.create(
            organization=organization,
            actor=actor,
            action="apply_schedule",
            reason=reason if conflicts else "",
            changes={
                "added": [
                    serialized_assignment(obj)
                    for obj in assignment_query(organization).filter(pk__in=[r.pk for r in records])
                ],
                "removed": removed,
                "conflicts": conflicts,
                "copy": preview["metadata"],
            },
        )
    return {
        "added": len(records),
        "removed": len(removed),
        "preserved": preserved,
        "revision": revision(organization, payload["dates"]),
        "assignments": [
            serialized_assignment(obj)
            for obj in assignment_query(organization).filter(date__in=payload["dates"])
        ],
    }


def copy_preview(organization, actor, data):
    source_week = data["source_week"]
    source = list(
        assignment_query(organization).filter(date__gte=source_week, date__lt=source_week + timedelta(days=7))
    )
    metadata = {
        "mode": data["mode"],
        "source_week": str(source_week),
        "source_dates": [str(source_week + timedelta(days=offset)) for offset in range(7)],
        "source_times": {},
    }
    if data["mode"] == "week":
        first = data["target_week"]
        end = first + timedelta(days=6)
        metadata["target_week"] = str(first)
    else:
        jalali_first = jdatetime.date(data["jalali_year"], data["jalali_month"], 1)
        next_month = jdatetime.date(
            jalali_first.year + (jalali_first.month == 12), jalali_first.month % 12 + 1, 1
        )
        first, end = jalali_first.togregorian(), next_month.togregorian() - timedelta(days=1)
        metadata.update({"jalali_year": jalali_first.year, "jalali_month": jalali_first.month})
    metadata.update({"target_start": str(first), "target_end": str(end)})
    specs = []
    by_weekday = defaultdict(list)
    for item in source:
        by_weekday[item.date.weekday()].append(item)
    current = first
    while current <= end:
        for item in by_weekday[current.weekday()]:
            metadata["source_times"][str(len(specs))] = [
                item.start_time.isoformat(),
                item.end_time.isoformat(),
            ]
            specs.append(
                {
                    "date": current,
                    "hall": item.hall_id,
                    "shift": item.shift_id,
                    "supervisor": item.supervisor_id,
                }
            )
        current += timedelta(days=1)
    if len(specs) > 5000:
        raise ValidationError("این الگو بیش از ۵۰۰۰ تخصیص می‌سازد؛ تعداد سالن‌ها یا مراقبان الگو را کاهش دهید.")
    return build_preview(organization, actor, specs, metadata=metadata)
