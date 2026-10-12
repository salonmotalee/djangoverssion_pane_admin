"""Shared business rules; mutation callers hold an atomic transaction."""

import hashlib
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AuditLog, LoginThrottle, User

CUSTOMER_FIELDS = (
    "name",
    "manager_name",
    "phone",
    "identifier",
    "slug",
    "capacity",
    "start_date",
    "expiration_date",
    "deleted_at",
)
USER_FIELDS = ("username", "first_name", "last_name", "email", "role", "is_active")


def snapshot(instance, fields):
    result = {}
    for field in fields:
        value = getattr(instance, field)
        result[field] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return result


def record_audit(actor, action, entity, description, before=None, fields=None):
    changes = {}
    if fields:
        after = snapshot(entity, fields)
        if before is None:
            changes = {key: {"after": value} for key, value in after.items()}
        else:
            changes = {
                key: {"before": before[key], "after": value}
                for key, value in after.items()
                if before[key] != value
            }
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type="customer" if entity.__class__.__name__ == "Customer" else "user",
        entity_id=str(entity.pk),
        description=description,
        changes=changes,
    )


def lock_and_guard_user(target, role=None, is_active=None, deleting=False):
    # All competing removals share ordered locks, preserving at least one active super.
    locked = list(
        User.objects.select_for_update()
        .filter(Q(role=User.Role.SUPER_ADMIN, is_active=True) | Q(pk=target.pk))
        .order_by("pk")
    )
    target = next(user for user in locked if user.pk == target.pk)
    losing_super = deleting or role not in (None, User.Role.SUPER_ADMIN) or is_active is False
    if target.role == User.Role.SUPER_ADMIN and target.is_active and losing_super:
        supers = [user for user in locked if user.role == User.Role.SUPER_ADMIN and user.is_active]
        if len(supers) <= 1:
            raise ValidationError({"detail": "آخرین مدیر ارشد فعال قابل حذف، غیرفعال‌سازی یا تغییر نقش نیست."})
    return target


def throttle_keys(request, username):
    # REMOTE_ADDR is supplied by the server. Never trust arbitrary forwarded headers.
    values = [("account:" + username.casefold(), 5), ("ip:" + request.META.get("REMOTE_ADDR", "unknown"), 20)]
    return [(hashlib.sha256(value.encode()).hexdigest(), limit) for value, limit in values]


def throttle_records(keys):
    now = timezone.now()
    records = []
    for key, limit in sorted(keys):
        item, _ = LoginThrottle.objects.get_or_create(key=key)
        item = LoginThrottle.objects.select_for_update().get(pk=item.pk)
        lock_expired = item.locked_until is not None and item.locked_until <= now
        window_expired = item.locked_until is None and now - item.window_started_at >= timedelta(minutes=15)
        if lock_expired or window_expired:
            item.failures = 0
            item.window_started_at = now
            item.locked_until = None
            item.save()
        records.append((item, limit))
    return records


def login_is_limited(records):
    now = timezone.now()
    return any(item.locked_until and item.locked_until > now for item, _ in records)


def failed_login(records):
    now = timezone.now()
    for item, limit in records:
        item.failures += 1
        if item.failures >= limit:
            item.locked_until = now + timedelta(minutes=15)
        item.save()


def successful_login(records, account_key):
    # A valid account clears its own failures, but not the IP's attacks on other accounts.
    for item, _ in records:
        if item.key == account_key:
            item.failures = 0
            item.locked_until = None
            item.window_started_at = timezone.now()
            item.save()
