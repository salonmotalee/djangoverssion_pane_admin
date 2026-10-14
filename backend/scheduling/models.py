"""Tenant-owned operational planning; assignment times are immutable snapshots."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from operations.models import OrganizationRecord, SupervisorHall


class WorkShift(OrganizationRecord):
    name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["start_time", "end_time", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="shift_same_day_order")
        ]
        indexes = [models.Index(fields=["organization", "is_active"], name="shift_org_active_idx")]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "پایان شیفت باید بعد از شروع، در همان روز باشد."})


class ScheduleAssignment(models.Model):
    organization = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    date = models.DateField()
    hall = models.ForeignKey("operations.Hall", on_delete=models.PROTECT, related_name="work_assignments")
    shift = models.ForeignKey(WorkShift, on_delete=models.PROTECT, related_name="assignments")
    supervisor = models.ForeignKey(
        "operations.Supervisor", on_delete=models.PROTECT, related_name="work_assignments"
    )
    # Editing a reusable shift never changes committed schedules without preview.
    start_time = models.TimeField()
    end_time = models.TimeField()
    shift_name = models.CharField(max_length=120)
    conflict_override = models.BooleanField(default=False)
    override_reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time", "hall_id", "supervisor_id", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "date", "hall", "shift", "supervisor"],
                name="schedule_assignment_unique",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="assignment_same_day_order"
            ),
            models.CheckConstraint(
                condition=Q(conflict_override=False) | ~Q(override_reason=""), name="schedule_override_reason"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "date"], name="schedule_org_date_idx"),
            models.Index(fields=["supervisor", "date"], name="schedule_staff_date_idx"),
        ]

    def clean(self):
        super().clean()
        if not all((self.hall_id, self.shift_id, self.supervisor_id, self.organization_id)):
            return
        if any(
            item.organization_id != self.organization_id for item in (self.hall, self.shift, self.supervisor)
        ):
            raise ValidationError("سالن، شیفت و مراقب باید متعلق به یک مجموعه باشند.")
        if not self.pk:
            if (
                not self.hall.is_active
                or not self.shift.is_active
                or not self.supervisor.is_active
                or self.supervisor.archived_at is not None
                or not SupervisorHall.objects.filter(
                    supervisor_id=self.supervisor_id, hall_id=self.hall_id
                ).exists()
            ):
                raise ValidationError("مراقب فعال باید به سالن فعال انتخاب‌شده تخصیص داشته باشد.")


class ScheduleAudit(models.Model):
    organization = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=32)
    reason = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["organization", "created_at"], name="schedule_audit_org_idx")]
