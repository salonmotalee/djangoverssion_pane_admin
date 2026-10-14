"""Every mutation holds the same Customer lock, including capacity edits centrally.

PostgreSQL serializes writers per organization using SELECT FOR UPDATE. SQLite
uses the existing IMMEDIATE transaction mode, acquiring its write lock before reads.
All capacity-sensitive operations must run inside this boundary, never count then
write outside it. No process-local mutexes or transient cache counters are used.
"""

from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

from core.models import Customer
from portal.views import owned_organization

from .models import Hall, Student, StudySession


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
        "students_per_hall": list(
            Hall.objects.filter(organization=organization, is_active=True)
            .annotate(active_students=Count("students", filter=Q(students__is_active=True)))
            .values("id", "name", "active_students")
        ),
    }
