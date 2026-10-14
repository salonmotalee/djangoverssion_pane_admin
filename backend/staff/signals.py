"""Revoked personnel/organization access never revives an old session."""

from django.db.models import F
from django.db.models.signals import pre_save
from django.dispatch import receiver

from core.models import Customer
from operations.models import Supervisor

from .models import SupervisorAccount


@receiver(pre_save, sender=Supervisor)
def revoke_changed_personnel(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or instance.pk is None:
        return
    relevant = {"phone", "is_active", "archived_at"}
    if update_fields is not None and not relevant.intersection(update_fields):
        return
    previous = sender.objects.filter(pk=instance.pk).values(*relevant).first()
    if previous and any(previous[field] != getattr(instance, field) for field in relevant):
        SupervisorAccount.objects.filter(supervisor_id=instance.pk).update(
            session_version=F("session_version") + 1
        )


@receiver(pre_save, sender=Customer)
def revoke_archived_organization(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or instance.pk is None or instance.deleted_at is None:
        return
    if update_fields is not None and "deleted_at" not in update_fields:
        return
    if sender.objects.filter(pk=instance.pk, deleted_at__isnull=True).exists():
        SupervisorAccount.objects.filter(organization_id=instance.pk).update(
            session_version=F("session_version") + 1
        )
