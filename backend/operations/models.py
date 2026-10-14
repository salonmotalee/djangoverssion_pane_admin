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


class SupervisorQuerySet(models.QuerySet):
    def update(self, **kwargs):
        # Unvalidated UPDATE would bypass phone, archive and immutable-tenant checks.
        raise ValidationError("برای ویرایش مراقب از ذخیرهٔ معتبر استفاده کنید.")

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        if update_conflicts:
            raise ValidationError("ویرایش مراقب با درج هم‌زمان مجاز نیست؛ از ذخیرهٔ معتبر استفاده کنید.")
        objs = list(objs)
        with transaction.atomic():
            for organization in (
                Customer.objects.select_for_update()
                .filter(pk__in={obj.organization_id for obj in objs})
                .order_by("pk")
            ):
                if organization.deleted_at is not None:
                    raise ValidationError("این مجموعه بایگانی شده است.")
            for obj in objs:
                obj.normalize_fields()
                obj.full_clean()
            return super().bulk_create(
                objs,
                batch_size=batch_size,
                ignore_conflicts=ignore_conflicts,
                update_conflicts=update_conflicts,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )

    def bulk_update(self, objs, fields, *args, **kwargs):
        # Ordinary save provides validation and the immutable tenant boundary.
        raise ValidationError("برای ویرایش مراقبین از ذخیرهٔ جداگانه استفاده کنید.")


class Supervisor(OrganizationRecord):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=11, validators=[phone_validator])
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    halls = models.ManyToManyField(Hall, through="SupervisorHall", related_name="supervisors")
    objects = SupervisorQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name", "pk"]
        indexes = [
            models.Index(
                fields=["organization", "archived_at", "is_active"], name="supervisor_org_status_idx"
            )
        ]

    def normalize_fields(self):
        # Match CustomerSerializer normalization for direct model writes too.
        if isinstance(self.first_name, str):
            self.first_name = self.first_name.strip()
        if isinstance(self.last_name, str):
            self.last_name = self.last_name.strip()
        if not isinstance(self.phone, str):
            return
        self.phone = (
            self.phone.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            .replace(" ", "")
            .replace("-", "")
        )
        if self.phone.startswith("+98"):
            self.phone = "0" + self.phone[3:]
        elif self.phone.startswith("0098"):
            self.phone = "0" + self.phone[4:]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            organization = Customer.objects.select_for_update().get(pk=self.organization_id)
            if organization.deleted_at is not None:
                raise ValidationError("این مجموعه بایگانی شده است.")
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("organization_id", "archived_at", "first_name", "last_name", "phone", "is_active")
                .first()
            )
            if previous and previous["organization_id"] != self.organization_id:
                raise ValidationError({"organization": "مجموعهٔ مراقب قابل تغییر نیست."})
            self.normalize_fields()
            if previous and previous["archived_at"] and self.archived_at is not None:
                if any(
                    previous[field] != getattr(self, field)
                    for field in ("first_name", "last_name", "phone", "is_active")
                ):
                    raise ValidationError("ابتدا مراقب بایگانی‌شده را بازیابی کنید.")
            self.full_clean()
            return super().save(*args, **kwargs)


class SupervisorHallQuerySet(models.QuerySet):
    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        # Django's forward/reverse ManyRelatedManager.add() also uses this path.
        if update_conflicts:
            raise ValidationError("ویرایش تخصیص با درج هم‌زمان مجاز نیست؛ از ذخیرهٔ معتبر استفاده کنید.")
        objs = list(objs)
        with transaction.atomic():
            organizations = Supervisor.objects.filter(pk__in={obj.supervisor_id for obj in objs}).values_list(
                "organization_id", flat=True
            )
            list(Customer.objects.select_for_update().filter(pk__in=organizations).order_by("pk"))
            for obj in objs:
                obj.full_clean()
            return super().bulk_create(
                objs,
                batch_size=batch_size,
                ignore_conflicts=ignore_conflicts,
                update_conflicts=update_conflicts,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )

    def update(self, **kwargs):
        if {"supervisor", "supervisor_id", "hall", "hall_id"} & kwargs.keys():
            raise ValidationError("برای تغییر تخصیص مراقب از ذخیرهٔ معتبر استفاده کنید.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        raise ValidationError("برای تغییر تخصیص مراقب از ذخیرهٔ معتبر استفاده کنید.")


class SupervisorHall(models.Model):
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="hall_assignments")
    hall = models.ForeignKey(Hall, on_delete=models.PROTECT, related_name="supervisor_assignments")
    objects = SupervisorHallQuerySet.as_manager()

    class Meta:
        ordering = ["hall__name", "hall_id", "supervisor_id"]
        constraints = [models.UniqueConstraint(fields=["supervisor", "hall"], name="supervisor_hall_unique")]

    def clean(self):
        super().clean()
        if not self.supervisor_id or not self.hall_id:
            return
        supervisor = Supervisor.objects.filter(pk=self.supervisor_id).first()
        hall = Hall.objects.filter(pk=self.hall_id).first()
        if supervisor is None or hall is None:
            raise ValidationError("مراقب یا سالن یافت نشد.")
        if supervisor.organization_id != hall.organization_id:
            raise ValidationError("مراقب و سالن باید متعلق به یک مجموعه باشند.")
        # Existing links remain as history when either record is archived.
        previous = type(self).objects.filter(pk=self.pk).values("supervisor_id", "hall_id").first()
        unchanged = previous and previous == {"supervisor_id": self.supervisor_id, "hall_id": self.hall_id}
        if not unchanged and (supervisor.archived_at is not None or not hall.is_active):
            raise ValidationError("تخصیص جدید به مراقب یا سالن بایگانی‌شده مجاز نیست.")
        if supervisor.organization.deleted_at is not None:
            raise ValidationError("این مجموعه بایگانی شده است.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            organization_id = Supervisor.objects.values_list("organization_id", flat=True).get(
                pk=self.supervisor_id
            )
            Customer.objects.select_for_update().get(pk=organization_id)
            self.full_clean()
            return super().save(*args, **kwargs)
