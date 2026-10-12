"""Internal users, customers and a deliberately non-secret audit trail."""

import secrets

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class InternalUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = User.Role.SUPER_ADMIN
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "مدیر ارشد"
        ADMIN = "admin", "مدیر"
        OPERATOR = "operator", "اپراتور"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OPERATOR, db_index=True)
    objects = InternalUserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["super_admin", "admin", "operator"]), name="user_valid_role"
            ),
            models.CheckConstraint(
                condition=(
                    Q(role="super_admin", is_superuser=True)
                    | (~Q(role="super_admin") & Q(is_superuser=False))
                ),
                name="user_super_role_consistent",
            ),
        ]

    def save(self, *args, **kwargs):
        self.is_superuser = self.role == self.Role.SUPER_ADMIN
        self.is_staff = self.role in {self.Role.SUPER_ADMIN, self.Role.ADMIN}
        if kwargs.get("update_fields") is not None:
            update_fields = set(kwargs["update_fields"])
            # Django's last_login signal must not rewrite privilege flags from a
            # user instance loaded before a concurrent role change.
            if update_fields & {"role", "is_superuser", "is_staff"}:
                update_fields |= {"is_superuser", "is_staff"}
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)


def generate_identifier():
    # Public integration identifier; this value grants no authentication access.
    return "NV" + secrets.token_hex(8).upper()


phone_validator = RegexValidator(r"^09[0-9]{9}$", "شماره همراه باید با ۰۹ آغاز شود و ۱۱ رقم داشته باشد.")
identifier_validator = RegexValidator(
    r"^[A-Za-z0-9]{4,32}$", "شناسه باید بین ۴ تا ۳۲ حرف یا رقم انگلیسی باشد."
)


class Customer(models.Model):
    name = models.CharField(max_length=180)
    manager_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=11, validators=[phone_validator])
    identifier = models.CharField(
        max_length=32, unique=True, default=generate_identifier, validators=[identifier_validator]
    )
    start_date = models.DateField(db_index=True)
    expiration_date = models.DateField(db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["deleted_at", "expiration_date"], name="customer_expiry_idx"),
            models.Index(fields=["deleted_at", "created_at"], name="customer_recent_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expiration_date__gte=F("start_date")), name="customer_date_order"
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.expiration_date and self.start_date and self.expiration_date < self.start_date:
            raise ValidationError({"expiration_date": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."})
        if self.pk and type(self).objects.filter(pk=self.pk).exclude(identifier=self.identifier).exists():
            raise ValidationError({"identifier": "شناسه مشتری پس از ایجاد قابل تغییر نیست."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        return (self.expiration_date - timezone.localdate()).days

    @property
    def status(self):
        today = timezone.localdate()
        if self.start_date > today:
            return "scheduled"
        days = (self.expiration_date - today).days
        if days < 0:
            return "expired"
        if days <= 30:
            return "expiring"
        return "active"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_events")
    action = models.CharField(max_length=40, db_index=True)
    entity_type = models.CharField(max_length=30)
    entity_id = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=300)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx")]


class LoginThrottle(models.Model):
    """Persistent counters shared across workers; keys contain hashes, not usernames."""

    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True, blank=True)
