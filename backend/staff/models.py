"""Login identities are separate from non-unique supervisor personnel records."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils.crypto import salted_hmac

from core.models import Customer, phone_validator
from operations.models import Supervisor


def normalized_phone(value):
    value = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    value = value.replace(" ", "").replace("-", "")
    if value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("0098"):
        value = "0" + value[4:]
    phone_validator(value)
    return value


class SupervisorAccountManager(BaseUserManager):
    def create_user(self, supervisor, password=None, **extra_fields):
        account = self.model(
            supervisor=supervisor,
            organization_id=supervisor.organization_id,
            phone=normalized_phone(supervisor.phone),
            **extra_fields,
        )
        account.set_password(password)
        account.save(using=self._db)
        return account


class SupervisorAccount(AbstractBaseUser):
    organization = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="supervisor_accounts")
    supervisor = models.OneToOneField(Supervisor, on_delete=models.PROTECT, related_name="login_account")
    phone = models.CharField(max_length=11, validators=[phone_validator])
    is_active = models.BooleanField(default=True)
    session_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    provisioned_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="provisioned_supervisors"
    )
    objects = SupervisorAccountManager()
    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    role = "supervisor"
    is_staff = False
    is_superuser = False

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "phone"],
                condition=Q(is_active=True),
                name="staff_active_org_phone_unique",
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"], name="staff_org_active_idx")]

    @property
    def username(self):
        return self.phone

    @property
    def first_name(self):
        return self.supervisor.first_name

    @property
    def last_name(self):
        return self.supervisor.last_name

    @property
    def access_is_valid(self):
        return bool(
            self.is_active
            and self.has_usable_password()
            and self.organization.deleted_at is None
            and self.supervisor.organization_id == self.organization_id
            and self.supervisor.is_active
            and self.supervisor.archived_at is None
            and self.phone == self.supervisor.phone
        )

    def clean(self):
        super().clean()
        self.phone = normalized_phone(self.phone)
        supervisor = Supervisor.objects.filter(pk=self.supervisor_id).first()
        if supervisor is None or supervisor.organization_id != self.organization_id:
            raise ValidationError({"supervisor": "مراقب باید متعلق به همین مجموعه باشد."})
        if self.is_active and (not supervisor.is_active or supervisor.archived_at is not None):
            raise ValidationError({"is_active": "ابتدا مراقب را فعال و از بایگانی بازیابی کنید."})
        if self.phone != supervisor.phone:
            raise ValidationError({"phone": "نام کاربری باید شمارهٔ همراه فعلی مراقب باشد."})

    def save(self, *args, **kwargs):
        # This lock also serializes concurrent provisioning of duplicate personnel
        # phone numbers; the partial unique constraint is the final DB invariant.
        with transaction.atomic():
            organization = Customer.objects.select_for_update().get(pk=self.organization_id)
            if organization.deleted_at is not None:
                raise ValidationError("این مجموعه بایگانی شده است.")
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "organization_id", "supervisor_id", "phone", "password", "is_active", "session_version"
                )
                .first()
            )
            if previous and (
                previous["organization_id"] != self.organization_id
                or previous["supervisor_id"] != self.supervisor_id
            ):
                raise ValidationError("مراقب و مجموعهٔ حساب ورود قابل تغییر نیستند.")
            # last_login writes must not overwrite a concurrently reset credential.
            fields = kwargs.get("update_fields")
            if fields is not None and set(fields) == {"last_login"}:
                return super().save(*args, **kwargs)
            self.phone = normalized_phone(self.phone)
            if previous and any(
                previous[key] != getattr(self, key) for key in ("phone", "password", "is_active")
            ):
                self.session_version = previous["session_version"] + 1
                if fields is not None:
                    kwargs["update_fields"] = set(fields) | {"session_version"}
            self.full_clean()
            return super().save(*args, **kwargs)

    def _get_session_auth_hash(self, secret=None):
        return salted_hmac(
            "damavand.supervisor.session",
            f"{self.password}:{self.session_version}",
            secret=secret,
            algorithm="sha256",
        ).hexdigest()
