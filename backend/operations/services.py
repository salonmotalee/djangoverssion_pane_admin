"""Every mutation holds the same Customer lock, including capacity edits centrally.

PostgreSQL serializes writers per organization using SELECT FOR UPDATE. SQLite
uses the existing IMMEDIATE transaction mode, acquiring its write lock before reads.
All capacity-sensitive operations must run inside this boundary, never count then
write outside it. No process-local mutexes or transient cache counters are used.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import Customer
from portal.views import owned_organization

from .models import Hall, Student, StudySession, Supervisor, SupervisorHall


def lock_organization(request, slug):
    organization = owned_organization(request, slug)
    locked = Customer.objects.select_for_update().get(pk=organization.pk)
    if locked.deleted_at is not None:
        raise ValidationError("این مجموعه بایگانی شده است.")
    return locked


def capacity_summary(organization):
    active = Student.objects.filter(organization=organization, is_active=True).count()
    capacity = organization.capacity
    return {
        "capacity": capacity,
        "active_students": active,
        "remaining_capacity": max(0, capacity - active) if capacity is not None else None,
        "utilization_percent": round(active * 100 / capacity, 1) if capacity else None,
        "over_capacity": capacity is not None and active > capacity,
        "active_halls": Hall.objects.filter(organization=organization, is_active=True).count(),
        "active_sessions": StudySession.objects.filter(organization=organization, is_active=True).count(),
        "active_supervisors": Supervisor.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).count(),
        "students_per_hall": list(
            Hall.objects.filter(organization=organization, is_active=True)
            .annotate(active_students=Count("students", filter=Q(students__is_active=True)))
            .values("id", "name", "active_students")
        ),
    }


@transaction.atomic
def assign_supervisor_halls(supervisor, halls):
    organization = Customer.objects.select_for_update().get(pk=supervisor.organization_id)
    if organization.deleted_at is not None:
        raise ValidationError("این مجموعه بایگانی شده است.")
    current = Supervisor.objects.select_for_update().get(pk=supervisor.pk, organization=organization)
    if current.archived_at is not None:
        raise ValidationError("ابتدا مراقب بایگانی‌شده را بازیابی کنید.")
    hall_ids = [hall.pk for hall in halls]
    selected = list(Hall.objects.filter(pk__in=hall_ids, organization=organization, is_active=True))
    if len(selected) != len(hall_ids):
        raise ValidationError({"halls": "سالن نامعتبر، متعلق به مجموعهٔ دیگر یا بایگانی‌شده است."})
    # Retain historical archived-hall assignments, replacing active selections only.
    current.hall_assignments.filter(hall__is_active=True).exclude(hall_id__in=hall_ids).delete()
    existing = set(current.hall_assignments.values_list("hall_id", flat=True))
    SupervisorHall.objects.bulk_create(
        [SupervisorHall(supervisor=current, hall=hall) for hall in selected if hall.pk not in existing]
    )
    supervisor._prefetched_objects_cache = {}


@transaction.atomic
def change_supervisor_status(supervisor, action):
    organization = Customer.objects.select_for_update().get(pk=supervisor.organization_id)
    if organization.deleted_at is not None:
        raise ValidationError("این مجموعه بایگانی شده است.")
    current = Supervisor.objects.select_for_update().get(pk=supervisor.pk, organization=organization)
    if action in {"activate", "deactivate"}:
        if current.archived_at is not None:
            raise ValidationError("ابتدا مراقب بایگانی‌شده را بازیابی کنید.")
        current.is_active = action == "activate"
        fields = ["is_active", "updated_at"]
    elif action == "archive":
        # Preserve the activation flag: restoration does not activate inactive staff.
        current.archived_at = current.archived_at or timezone.now()
        fields = ["archived_at", "updated_at"]
    elif action == "restore":
        current.archived_at = None
        fields = ["archived_at", "updated_at"]
    else:
        raise ValidationError("عملیات انتخاب‌شده معتبر نیست.")
    current.save(update_fields=fields)
    return current
