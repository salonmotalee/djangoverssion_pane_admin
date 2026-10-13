from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import AuditLog, Customer, User, generate_identifier


def check_password(password, user=None):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return password


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=[(choice, label) for choice, label in User.Role.choices if choice != "tenant"], required=False
    )
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "date_joined",
            "last_login",
            "password",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def validate(self, attrs):
        forbidden = {
            "is_superuser",
            "is_staff",
            "groups",
            "user_permissions",
            "organization",
            "organization_id",
            "portal_username",
            "is_portal_owner",
            "portal_session_version",
        } & set(self.initial_data)
        if forbidden:
            raise serializers.ValidationError({key: "این فیلد مستقیماً قابل تغییر نیست." for key in forbidden})
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "رمز عبور برای کاربر جدید الزامی است."})
        if self.instance is not None and "password" in attrs:
            raise serializers.ValidationError(
                {"password": "برای تغییر رمز از عملیات بازنشانی رمز استفاده کنید."}
            )
        request = self.context.get("request")
        if (
            request
            and request.user.role == User.Role.ADMIN
            and attrs.get("role", User.Role.OPERATOR) != User.Role.OPERATOR
        ):
            raise serializers.ValidationError({"role": "مدیر فقط می‌تواند اپراتور ایجاد یا مدیریت کند."})
        if "password" in attrs:
            candidate = User(**{key: value for key, value in attrs.items() if key != "password"})
            check_password(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate(self, attrs):
        extras = set(self.initial_data) - set(self.fields)
        if extras:
            raise serializers.ValidationError({key: "این فیلد در پروفایل قابل تغییر نیست." for key in extras})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("رمز عبور فعلی صحیح نیست.")
        return value

    def validate_new_password(self, value):
        return check_password(value, self.context["request"].user)


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_new_password(self, value):
        return check_password(value, self.context["user"])


class CustomerSerializer(serializers.ModelSerializer):
    identifier = serializers.CharField(required=False, allow_blank=True, max_length=32)
    status = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    phone = serializers.CharField(max_length=20)
    slug = serializers.CharField(required=False, max_length=48)
    capacity = serializers.IntegerField(min_value=1, max_value=2147483647, required=False, allow_null=True)
    login_username = serializers.CharField(required=False, max_length=64)
    login_password = serializers.CharField(
        required=False, write_only=True, trim_whitespace=False, max_length=4096
    )
    portal_provisioned = serializers.SerializerMethodField()
    portal_is_active = serializers.SerializerMethodField()
    portal_url = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "manager_name",
            "phone",
            "identifier",
            "slug",
            "capacity",
            "login_username",
            "login_password",
            "portal_provisioned",
            "portal_is_active",
            "portal_url",
            "subscription",
            "start_date",
            "expiration_date",
            "deleted_at",
            "created_at",
            "updated_at",
            "status",
            "days_remaining",
        ]
        read_only_fields = ["id", "deleted_at", "created_at", "updated_at", "status", "days_remaining"]

    def to_representation(self, instance):
        # Credentials live on the existing Django User, never on the customer row.
        result = super().to_representation(instance)
        owner = instance.portal_owner
        request = self.context.get("request")
        result["login_username"] = (
            owner.portal_username
            if owner and request and request.user.role in {"super_admin", "admin"}
            else None
        )
        return result

    def get_portal_provisioned(self, customer):
        return customer.portal_owner is not None

    def get_portal_is_active(self, customer):
        owner = customer.portal_owner
        return bool(owner and owner.is_active and not customer.deleted_at)

    def get_portal_url(self, customer):
        from django.conf import settings

        return f"{settings.FRONTEND_URL.rstrip('/')}/{customer.slug}"

    def get_subscription(self, customer):
        from portal.services import subscription

        return subscription(customer)

    def validate_slug(self, value):
        from .routing import validate_portal_slug

        try:
            validate_portal_slug(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if self.instance and self.instance.slug != value:
            raise serializers.ValidationError("نشانی پرتال پس از ایجاد قابل تغییر نیست.")
        if (
            Customer.objects.filter(slug=value)
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise serializers.ValidationError("این نشانی قبلاً استفاده شده است.")
        return value

    def validate_identifier(self, value):
        if self.instance:
            if value != self.instance.identifier:
                raise serializers.ValidationError("شناسه مشتری پس از ایجاد قابل تغییر نیست.")
            return value
        value = value or generate_identifier()
        from .models import identifier_validator

        try:
            identifier_validator(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if Customer.objects.filter(identifier=value).exists():
            raise serializers.ValidationError("این شناسه قبلاً استفاده شده است.")
        return value

    def validate_phone(self, value):
        digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        value = value.translate(digits).replace(" ", "").replace("-", "")
        if value.startswith("+98"):
            value = "0" + value[3:]
        elif value.startswith("0098"):
            value = "0" + value[4:]
        from .models import phone_validator

        try:
            phone_validator(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", self.instance.start_date if self.instance else None)
        end = attrs.get("expiration_date", self.instance.expiration_date if self.instance else None)
        if start and end and end < start:
            raise serializers.ValidationError(
                {"expiration_date": "تاریخ پایان باید برابر یا بعد از تاریخ شروع باشد."}
            )
        if self.instance and self.instance.deleted_at:
            raise serializers.ValidationError("ابتدا مشتری حذف‌شده را بازیابی کنید.")
        if "deleted_at" in self.initial_data:
            raise serializers.ValidationError(
                {"deleted_at": "برای حذف یا بازیابی از عملیات مربوط استفاده کنید."}
            )
        if "capacity" in attrs and (
            attrs["capacity"] is None or isinstance(self.initial_data.get("capacity"), bool)
        ):
            raise serializers.ValidationError({"capacity": "ظرفیت باید عدد مثبت باشد."})
        if "login_username" in attrs or "login_password" in attrs:
            request = self.context.get("request")
            if not request or request.user.role not in {"admin", "super_admin"}:
                raise serializers.ValidationError(
                    {"login_username": "فقط مدیران می‌توانند ورود پرتال را راه‌اندازی کنند."}
                )
            if self.instance:
                raise serializers.ValidationError(
                    {"login_password": "برای تغییر دسترسی از بخش تنظیم ورود پرتال استفاده کنید."}
                )
            from portal.serializers import PortalCredentialsSerializer

            portal = PortalCredentialsSerializer(
                data={
                    key: attrs[key]
                    for key in ("login_username", "login_password", "capacity")
                    if key in attrs
                }
            )
            portal.is_valid(raise_exception=True)
            if (
                not portal.validated_data.get("login_username")
                or not portal.validated_data.get("login_password")
                or not attrs.get("capacity")
            ):
                raise serializers.ValidationError(
                    {"login_password": "نام کاربری، رمز قوی و ظرفیت برای راه‌اندازی پرتال الزامی است."}
                )
            check_password(attrs["login_password"], User(username=portal.validated_data["login_username"]))
            attrs["login_username"] = portal.validated_data["login_username"]
        return attrs

    def create(self, validated_data):
        from django.db import transaction

        from portal.services import provision_portal

        portal_data = {
            key: validated_data.pop(key)
            for key in ("login_username", "login_password")
            if key in validated_data
        }
        try:
            with transaction.atomic():
                customer = super().create(validated_data)
                if portal_data:
                    provision_portal(customer, portal_data, self.context["request"].user)
                return customer
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class RenewalSerializer(serializers.Serializer):
    expiration_date = serializers.DateField()

    def validate_expiration_date(self, value):
        customer = self.context["customer"]
        if value <= customer.expiration_date:
            raise serializers.ValidationError("تاریخ جدید باید بعد از پایان فعلی باشد.")
        if value < timezone.localdate():
            raise serializers.ValidationError("تاریخ جدید نمی‌تواند در گذشته باشد.")
        return value


class AuditActorSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    def get_username(self, user):
        return user.portal_username if user.role == User.Role.TENANT else user.username

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class AuditSerializer(serializers.ModelSerializer):
    actor = AuditActorSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "action", "entity_type", "entity_id", "description", "changes", "created_at"]
