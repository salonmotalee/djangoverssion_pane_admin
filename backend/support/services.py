"""All conversation changes are atomic and serialize on the ticket row."""

from django.utils import timezone

from core.models import AuditLog, User

from .models import Message, Notification, StatusEvent
from .permissions import support_staff


def author_name(user):
    return user.get_full_name().strip() or (
        user.portal_username if user.role == User.Role.TENANT else user.username
    )


def recipients(ticket, actor):
    if actor.role == User.Role.TENANT:
        return support_staff().exclude(pk=actor.pk)
    return User.objects.filter(
        organization=ticket.organization,
        role=User.Role.TENANT,
        is_active=True,
        is_portal_owner=True,
    ).exclude(pk=actor.pk)


def audit(ticket, actor, action, description, changes=None):
    AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type="support_ticket",
        entity_id=str(ticket.pk),
        description=description,
        changes=changes or {},
    )


def add_message(ticket, actor, body):
    message = Message.objects.create(
        ticket=ticket,
        author=actor,
        author_name=author_name(actor),
        author_role=actor.role,
        body=body,
    )
    Notification.objects.bulk_create(
        [
            Notification(recipient=user, ticket=ticket, message=message, kind="message", body=body[:300])
            for user in recipients(ticket, actor)
        ]
    )
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["updated_at"])
    return message


def set_status(ticket, actor, new_status, *, initial=False):
    previous = "" if initial else ticket.status
    if previous == new_status:
        return
    event = StatusEvent.objects.create(
        ticket=ticket,
        actor=actor,
        actor_name=author_name(actor),
        previous_status=previous,
        status=new_status,
    )
    ticket.status = new_status
    ticket.save(update_fields=["status", "updated_at"])
    if not initial:
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=user,
                    ticket=ticket,
                    status_event=event,
                    kind="status",
                    body=f"وضعیت تیکت به «{ticket.get_status_display()}» تغییر کرد.",
                )
                for user in recipients(ticket, actor)
            ]
        )
    audit(
        ticket,
        actor,
        "support_create" if initial else "support_status",
        "ایجاد تیکت پشتیبانی" if initial else f"تغییر وضعیت تیکت به {ticket.get_status_display()}",
        {"status": {"before": previous, "after": new_status}},
    )
