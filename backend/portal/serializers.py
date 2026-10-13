from rest_framework import serializers

from core.models import Customer

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

    class Meta:
        model = Customer
        fields = ["name", "manager_name", "phone", "identifier", "slug", "capacity", "subscription"]

    def get_subscription(self, customer):
        return subscription(customer)
