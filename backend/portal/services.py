"""Provision real Django identities attached to existing customer organizations."""

import secrets
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.models import Customer, User
from core.serializers import check_password
from core.services import record_audit


def subscription(customer, today=None):
    today = today or timezone.localdate(timezone=ZoneInfo("Asia/Tehran"))
    total = (customer.expiration_date - customer.start_date).days + 1
    elapsed = min(total, max(0, (today - customer.start_date).days))
    remaining = max(0, total - elapsed)
    status = (
        "scheduled"
        if today < customer.start_date
        else "expired"
        if today > customer.expiration_date
        else "expiring"
        if (customer.expiration_date - today).days <= 30
        else "active"
    )
    return {
        "start_date": customer.start_date,
        "expiration_date": customer.expiration_date,
        "status": status,
        "remaining_days": remaining,
        "total_days": total,
        "elapsed_days": elapsed,
        "progress_percent": round(100 * elapsed / total, 1),
        "days_until_start": max(0, (customer.start_date - today).days),
        "days_since_expiration": max(0, (today - customer.expiration_date).days),
        "business_date": today,
        "end_date_inclusive": True,
    }


def provision_portal(customer, data, actor=None):
    # The customer row is the serialization point for provisioning and deletion.
    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        if customer.deleted_at:
            raise serializers.ValidationError("ابتدا مجموعه حذف‌شده را بازیابی کنید.")
        capacity = data.get("capacity", customer.capacity)
        if capacity is None or isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise serializers.ValidationError({"capacity": "برای راه‌اندازی پرتال ظرفیت مثبت را مشخص کنید."})
        owner = User.objects.select_for_update().filter(organization=customer, is_portal_owner=True).first()
        username = data.get("login_username", owner.portal_username if owner else "")
        password = data.get("login_password")
        if not username or (owner is None and not password):
            raise serializers.ValidationError(
                {"login_password": "برای اولین ورود، نام کاربری و رمز قوی الزامی است."}
            )
        candidate = User(username=username, first_name=customer.manager_name)
        if password is not None:
            check_password(password, candidate)
        if owner is None:
            owner = User(
                username="tenant_" + secrets.token_hex(16),
                role=User.Role.TENANT,
                organization=customer,
                is_portal_owner=True,
                portal_username=username,
            )
        if User.objects.filter(organization=customer, portal_username=username).exclude(pk=owner.pk).exists():
            raise serializers.ValidationError({"login_username": "این نام کاربری در مجموعه استفاده شده است."})
        owner.portal_username = username
        owner.is_active = data.get("is_active", owner.is_active)
        owner.portal_session_version += 1  # Revoke old sessions on credentials/activation updates.
        if password:
            owner.set_password(password)
        owner.save()
        customer.capacity = capacity
        customer.save(update_fields=["capacity", "updated_at"])
        if actor is not None:
            record_audit(actor, "configure_portal", customer, f"تنظیم دسترسی پرتال {customer.name}")
        return owner
