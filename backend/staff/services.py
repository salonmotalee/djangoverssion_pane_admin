from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.models import AuditLog, Customer, User
from operations.models import Supervisor

from .models import SupervisorAccount, normalized_phone
from .permissions import authorized_halls


def access_payload(supervisor, account=None):
    return {
        "supervisor_id": supervisor.pk,
        "phone": supervisor.phone,
        "enabled": bool(account and account.is_active),
        "provisioned": account is not None,
        "usable": bool(account and account.access_is_valid),
        "account_id": account.pk if account else None,
        "last_login": account.last_login if account else None,
        "halls": list(
            authorized_halls(account).values("id", "name")
            if account
            else supervisor.halls.filter(is_active=True).values("id", "name")
        ),
    }


def check_password(password, account):
    try:
        validate_password(password, user=account)
    except DjangoValidationError as exc:
        raise ValidationError({"password": exc.messages}) from exc


def provision_supervisor(organization, supervisor_id, actor, enabled, password=None):
    try:
        with transaction.atomic():
            locked = Customer.objects.select_for_update().get(pk=organization.pk)
            # Role/access changes must not turn a stale manager session into a
            # credential-provisioning capability.
            if (
                locked.deleted_at is not None
                or not User.objects.filter(
                    pk=actor.pk,
                    role=User.Role.TENANT,
                    organization=locked,
                    is_active=True,
                    password=actor.password,
                    portal_session_version=actor.portal_session_version,
                ).exists()
            ):
                raise PermissionDenied("اجازهٔ تنظیم ورود مراقبین این مجموعه را ندارید.")
            from django.shortcuts import get_object_or_404

            supervisor = get_object_or_404(
                Supervisor.objects.select_for_update(), pk=supervisor_id, organization=locked
            )
            account = SupervisorAccount.objects.select_for_update().filter(supervisor=supervisor).first()
            before = {
                "enabled": bool(account and account.is_active),
                "phone": account.phone if account else None,
            }
            if enabled and (not supervisor.is_active or supervisor.archived_at is not None):
                raise ValidationError({"enabled": "ابتدا مراقب را فعال و از بایگانی بازیابی کنید."})
            if account is None:
                if enabled and not password:
                    raise ValidationError({"password": "برای فعال‌سازی اولیه، رمز عبور تعیین کنید."})
                if not enabled and password is None:
                    return access_payload(supervisor)
                account = SupervisorAccount(
                    organization=locked, supervisor=supervisor, phone=normalized_phone(supervisor.phone)
                )
                account.set_unusable_password()
            account.phone = normalized_phone(supervisor.phone)
            if (
                enabled
                and SupervisorAccount.objects.filter(organization=locked, phone=account.phone, is_active=True)
                .exclude(pk=account.pk)
                .exists()
            ):
                raise ValidationError(
                    {"enabled": "این شمارهٔ همراه برای ورود یک مراقب فعال دیگر استفاده شده است."}
                )
            if enabled and not account.has_usable_password() and password is None:
                raise ValidationError({"password": "برای فعال‌سازی، رمز عبور تعیین کنید."})
            if password is not None:
                check_password(password, account)
                account.set_password(password)
            account.is_active = enabled
            account.provisioned_by = actor
            account.save()
            AuditLog.objects.create(
                actor=actor,
                action="supervisor_access",
                entity_type="supervisor_account",
                entity_id=str(account.pk),
                description="تنظیم حساب ورود مراقب",
                changes={
                    "supervisor_id": supervisor.pk,
                    "enabled": {"before": before["enabled"], "after": enabled},
                    "phone": {"before": before["phone"], "after": account.phone},
                    "password_reset": password is not None,
                },
            )
            return access_payload(supervisor, account)
    except IntegrityError as exc:
        raise ValidationError({"enabled": "این شمارهٔ همراه دارای حساب ورود فعال در مجموعه است."}) from exc
    except DjangoValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
