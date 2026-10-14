"""Immutable presence history and independently owned attendance decisions."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class PresenceEvent(models.Model):
    class Kind(models.TextChoices):
        ENTRY = "entry", "ورود"
        EXIT = "exit", "خروج"

    organization = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    student = models.ForeignKey(
        "operations.Student", on_delete=models.PROTECT, related_name="presence_events"
    )
    hall = models.ForeignKey("operations.Hall", on_delete=models.PROTECT, related_name="presence_events")
    hall_name = models.CharField(max_length=160)
    actor = models.ForeignKey("staff.SupervisorAccount", on_delete=models.PROTECT)
    kind = models.CharField(max_length=5, choices=Kind.choices)
    sequence = models.PositiveIntegerField()
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["occurred_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["student", "sequence"], name="presence_student_sequence_unique"),
            models.CheckConstraint(condition=Q(kind__in=["entry", "exit"]), name="presence_kind_valid"),
            models.CheckConstraint(condition=Q(sequence__gte=1), name="presence_sequence_positive"),
        ]
        indexes = [
            models.Index(fields=["organization", "hall", "occurred_at"], name="presence_org_hall_time_idx"),
            models.Index(fields=["student", "occurred_at"], name="presence_student_time_idx"),
        ]

    def clean(self):
        super().clean()
        if any(
            item.organization_id != self.organization_id for item in (self.student, self.hall, self.actor)
        ):
            raise ValidationError("دانش‌آموز، سالن و مراقب باید متعلق به همین مجموعه باشند.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("تاریخچهٔ ورود و خروج قابل بازنویسی نیست.")
        self.clean()
        return super().save(*args, **kwargs)


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غایب"
        LATE = "late", "تأخیر"

    class Source(models.TextChoices):
        MANUAL = "manual", "دستی"
        AUTOMATIC = "automatic", "خودکار"

    organization = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    student = models.ForeignKey(
        "operations.Student", on_delete=models.PROTECT, related_name="attendance_records"
    )
    hall = models.ForeignKey("operations.Hall", on_delete=models.PROTECT, related_name="attendance_records")
    session = models.ForeignKey(
        "operations.StudySession", on_delete=models.PROTECT, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=7, choices=Status.choices)
    source = models.CharField(max_length=9, choices=Source.choices)
    original_recorder = models.ForeignKey("staff.SupervisorAccount", on_delete=models.PROTECT)
    hall_name = models.CharField(max_length=160)
    session_title = models.CharField(max_length=160, blank=True)
    session_start_time = models.TimeField()
    session_end_time = models.TimeField()
    early_departure = models.BooleanField(default=False)
    departed_at = models.DateTimeField(null=True, blank=True)
    # Reserved for a future individualized study roster; never inferred from client data.
    roster_context = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "session_start_time", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "hall", "session", "date", "student"], name="attendance_roster_unique"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["present", "absent", "late"]), name="attendance_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(source__in=["manual", "automatic"]), name="attendance_source_valid"
            ),
            models.CheckConstraint(condition=Q(revision__gte=1), name="attendance_revision_positive"),
            models.CheckConstraint(
                condition=Q(early_departure=False, departed_at__isnull=True)
                | Q(early_departure=True, departed_at__isnull=False),
                name="attendance_departure_consistent",
            ),
        ]
        indexes = [models.Index(fields=["organization", "hall", "date"], name="attendance_org_hall_date_idx")]

    def clean(self):
        super().clean()
        if any(
            item.organization_id != self.organization_id
            for item in (self.student, self.hall, self.session, self.original_recorder)
        ):
            raise ValidationError("حضور و غیاب باید در یک مجموعه ثبت شود.")
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            immutable = (
                "organization_id",
                "student_id",
                "hall_id",
                "session_id",
                "date",
                "original_recorder_id",
                "created_at",
                "hall_name",
                "session_title",
                "session_start_time",
                "session_end_time",
            )
            if previous and any(getattr(previous, key) != getattr(self, key) for key in immutable):
                raise ValidationError("مالک اولیه، زمان ایجاد و اطلاعات تاریخی حضور و غیاب قابل تغییر نیست.")

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class AttendanceAudit(models.Model):
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, related_name="audit_entries")
    acting_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    acting_supervisor = models.ForeignKey(
        "staff.SupervisorAccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attendance_changes",
    )
    original_recorder = models.ForeignKey("staff.SupervisorAccount", on_delete=models.PROTECT)
    previous = models.JSONField(default=dict)
    new = models.JSONField(default=dict)
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(acting_manager__isnull=False, acting_supervisor__isnull=True)
                | Q(acting_manager__isnull=True, acting_supervisor__isnull=False),
                name="attendance_audit_one_actor",
            )
        ]
