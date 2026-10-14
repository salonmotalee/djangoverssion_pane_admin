"""Persistent support conversations and recipient-specific notifications."""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Ticket(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "عمومی"
        TECHNICAL = "technical", "فنی"
        BILLING = "billing", "مالی"
        ACCOUNT = "account", "حساب کاربری"

    class Priority(models.TextChoices):
        LOW = "low", "کم"
        NORMAL = "normal", "عادی"
        HIGH = "high", "زیاد"
        URGENT = "urgent", "فوری"

    class Status(models.TextChoices):
        OPEN = "open", "باز"
        AWAITING_SUPPORT = "awaiting_support", "در انتظار پشتیبانی"
        AWAITING_CUSTOMER = "awaiting_customer", "در انتظار مجموعه"
        RESOLVED = "resolved", "حل‌شده"
        CLOSED = "closed", "بسته‌شده"

    organization = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="support_tickets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_support_tickets"
    )
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        indexes = [
            models.Index(fields=["organization", "-updated_at"], name="support_org_recent_idx"),
            models.Index(fields=["status", "-updated_at"], name="support_status_recent_idx"),
            models.Index(fields=["priority", "created_at"], name="support_priority_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["open", "awaiting_support", "awaiting_customer", "resolved", "closed"]
                ),
                name="support_valid_status",
            ),
            models.CheckConstraint(
                condition=Q(priority__in=["low", "normal", "high", "urgent"]), name="support_valid_priority"
            ),
            models.CheckConstraint(
                condition=Q(category__in=["general", "technical", "billing", "account"]),
                name="support_valid_category",
            ),
        ]


class Message(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="support_messages"
    )
    # Keep history intelligible after a user rename or account removal.
    author_name = models.CharField(max_length=301)
    author_role = models.CharField(max_length=20)
    body = models.TextField(max_length=10000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["ticket", "created_at", "id"], name="support_message_order_idx")]


class StatusEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="status_history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    actor_name = models.CharField(max_length=301)
    previous_status = models.CharField(max_length=24, blank=True)
    status = models.CharField(max_length=24, choices=Ticket.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class Notification(models.Model):
    class Kind(models.TextChoices):
        MESSAGE = "message", "پیام"
        STATUS = "status", "وضعیت"
        ASSIGNMENT = "assignment", "ارجاع"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_notifications"
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="notifications")
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True)
    status_event = models.ForeignKey(StatusEvent, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    body = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"], name="support_recipient_read_idx")
        ]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "message"], name="support_once_per_message"),
            models.UniqueConstraint(fields=["recipient", "status_event"], name="support_once_per_status"),
        ]
