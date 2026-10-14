from rest_framework import serializers

from core.models import Customer

from .appearance import default_appearance
from .services import subscription


class PortalCredentialsSerializer(serializers.Serializer):
    login_username = serializers.RegexField(
        r"^[a-zA-Z0-9][a-zA-Z0-9_.@+-]{2,63}$",
        required=False,
        max_length=64,
        error_messages={"invalid": "نام کاربری باید ۳ تا ۶۴ نویسه انگلیسی باشد."},
    )
    login_password = serializers.CharField(
        required=False, write_only=True, trim_whitespace=False, max_length=4096
    )
    capacity = serializers.IntegerField(min_value=1, max_value=2147483647, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_login_username(self, value):
        return value.casefold()

    def validate(self, attrs):
        if isinstance(self.initial_data.get("capacity"), bool):
            raise serializers.ValidationError({"capacity": "ظرفیت باید عدد صحیح مثبت باشد."})
        extras = set(self.initial_data) - set(self.fields)
        if extras:
            raise serializers.ValidationError(
                {name: "این فیلد برای تنظیم ورود مجاز نیست." for name in extras}
            )
        return attrs


class PortalProfileSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()
    appearance = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "name",
            "manager_name",
            "phone",
            "identifier",
            "slug",
            "capacity",
            "subscription",
            "appearance",
        ]

    def get_subscription(self, customer):
        return subscription(customer)

    def get_appearance(self, customer):
        return customer.appearance or default_appearance()


class StrictAppearanceSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["فقط تنظیمات ظاهر مشخص‌شده قابل تغییر هستند."]}
            )
        return super().to_internal_value(data)


class AppearancePaletteSerializer(StrictAppearanceSerializer):
    primary = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    background = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    surface = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    sidebar = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    success = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    warning = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)
    danger = serializers.RegexField(r"^#[0-9a-fA-F]{6}$", max_length=7)

    def validate(self, attrs):
        return {key: value.lower() for key, value in attrs.items()}


class AppearancePalettesSerializer(StrictAppearanceSerializer):
    light = AppearancePaletteSerializer()
    dark = AppearancePaletteSerializer()


class AppearanceSerializer(StrictAppearanceSerializer):
    version = serializers.ChoiceField(choices=[1])
    mode = serializers.ChoiceField(choices=["light", "dark", "system"])
    palettes = AppearancePalettesSerializer()

    def validate_version(self, value):
        if isinstance(self.initial_data.get("version"), bool):
            raise serializers.ValidationError("نسخهٔ تنظیمات معتبر نیست.")
        return value
