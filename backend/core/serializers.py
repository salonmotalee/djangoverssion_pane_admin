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
        forbidden = {"is_superuser", "is_staff", "groups", "user_permissions"} & set(self.initial_data)
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

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "manager_name",
            "phone",
            "identifier",
            "start_date",
            "expiration_date",
            "deleted_at",
            "created_at",
            "updated_at",
            "status",
            "days_remaining",
        ]
        read_only_fields = ["id", "deleted_at", "created_at", "updated_at", "status", "days_remaining"]

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
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
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
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class AuditSerializer(serializers.ModelSerializer):
    actor = AuditActorSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "action", "entity_type", "entity_id", "description", "changes", "created_at"]
