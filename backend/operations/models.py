"""Organization-owned operations. Archiving preserves student references and identifiers."""

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q

from core.models import Customer, phone_validator


class OrganizationRecord(models.Model):
    organization = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Hall(OrganizationRecord):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=2000)
    sessions = models.ManyToManyField("StudySession", through="HallSession", related_name="halls")

    class Meta:
        ordering = ["name", "pk"]
        indexes = [models.Index(fields=["organization", "is_active"], name="hall_org_active_idx")]


class StudySession(OrganizationRecord):
    title = models.CharField(max_length=160, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["start_time", "end_time", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="session_same_day_order")
        ]
        indexes = [models.Index(fields=["organization", "start_time"], name="session_org_time_idx")]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "ساعت پایان باید بعد از شروع، در همان روز باشد."})


class HallSession(models.Model):
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name="session_assignments")
    session = models.ForeignKey(StudySession, on_delete=models.CASCADE, related_name="hall_assignments")

    class Meta:
        ordering = ["session__start_time", "session__end_time", "session_id", "hall_id"]
        constraints = [models.UniqueConstraint(fields=["hall", "session"], name="hall_session_unique")]

    def clean(self):
        super().clean()
        if self.hall_id and self.session_id:
            if self.hall.organization_id != self.session.organization_id:
                raise ValidationError("سالن و پارت باید متعلق به یک مجموعه باشند.")
            if not self.hall.is_active or not self.session.is_active:
                raise ValidationError("تخصیص به سالن یا پارت بایگانی‌شده مجاز نیست.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Student(OrganizationRecord):
    class Grade(models.IntegerChoices):
        SEVENTH = 7, "هفتم"
        EIGHTH = 8, "هشتم"
        NINTH = 9, "نهم"
        TENTH = 10, "دهم"
        ELEVENTH = 11, "یازدهم"
        TWELFTH = 12, "دوازدهم"
        GRADUATE = 13, "فارغ‌التحصیل"

    class Major(models.TextChoices):
        HUMANITIES = "humanities", "علوم انسانی"
        MATHEMATICS = "mathematics", "ریاضی و فیزیک"
        EXPERIMENTAL = "experimental", "علوم تجربی"
        OTHER = "other", "سایر"

    identifier = models.CharField(max_length=64)
    desk_number = models.CharField(max_length=30, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    primary_phone = models.CharField(max_length=11, validators=[phone_validator])
    secondary_phone = models.CharField(max_length=11, blank=True, validators=[phone_validator])
    grade = models.PositiveSmallIntegerField(choices=Grade.choices)
    major = models.CharField(max_length=20, choices=Major.choices)
    hall = models.ForeignKey(Hall, on_delete=models.PROTECT, related_name="students")

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "identifier"], name="student_org_identifier_unique"
            ),
            models.CheckConstraint(
                condition=Q(grade__in=[7, 8, 9, 10, 11, 12, 13]), name="student_valid_grade"
            ),
            models.CheckConstraint(
                condition=Q(major__in=["humanities", "mathematics", "experimental", "other"]),
                name="student_valid_major",
            ),
        ]
        indexes = [models.Index(fields=["organization", "is_active", "hall"], name="student_org_hall_idx")]

    def clean(self):
        super().clean()
        if self.hall_id:
            hall = Hall.objects.get(pk=self.hall_id)
            if hall.organization_id != self.organization_id:
                raise ValidationError({"hall": "سالن باید متعلق به مجموعهٔ دانش‌آموز باشد."})
            if self.is_active and not hall.is_active:
                raise ValidationError({"hall": "دانش‌آموز فعال به سالن بایگانی‌شده منتقل نمی‌شود."})

    def save(self, *args, **kwargs):
        # Preserve the capacity invariant for ordinary ORM saves as well as REST
        # writes. QuerySet.update/bulk_create must never be used for enrollment.
        with transaction.atomic():
            organization = Customer.objects.select_for_update().get(pk=self.organization_id)
            if organization.deleted_at is not None:
                raise ValidationError("این مجموعه بایگانی شده است.")
            previous = type(self).objects.filter(pk=self.pk).values("organization_id", "is_active").first()
            if previous and previous["organization_id"] != self.organization_id:
                raise ValidationError({"organization": "مجموعهٔ دانش‌آموز قابل تغییر نیست."})
            self.clean()
            if self.is_active and (previous is None or not previous["is_active"]):
                count = type(self).objects.filter(organization=organization, is_active=True).count()
                if organization.capacity is None or count >= organization.capacity:
                    raise ValidationError("ظرفیت فعال مجموعه تکمیل است.")
            return super().save(*args, **kwargs)
