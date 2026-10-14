from rest_framework import serializers

from core.serializers import CustomerSerializer

from .models import Hall, Student, StudySession


def digits(value):
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class ScopedSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        extras = set(self.initial_data) - set(self.fields)
        readonly = set(self.initial_data) & set(self.Meta.read_only_fields)
        if extras or readonly:
            raise serializers.ValidationError({key: "این فیلد قابل تغییر نیست." for key in extras | readonly})
        return attrs


COMMON = ["id", "is_active", "created_at", "updated_at"]
READONLY = ["id", "created_at", "updated_at"]


class HallSerializer(ScopedSerializer):
    active_students = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Hall
        fields = [*COMMON, "name", "description", "active_students"]
        read_only_fields = [*READONLY, "active_students"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and attrs.get("is_active") is False:
            if self.instance.students.filter(is_active=True).exists():
                raise serializers.ValidationError(
                    {"is_active": "ابتدا دانش‌آموزان فعال سالن را منتقل یا بایگانی کنید."}
                )
        return attrs


class StudySessionSerializer(ScopedSerializer):
    class Meta:
        model = StudySession
        fields = [*COMMON, "title", "start_time", "end_time"]
        read_only_fields = READONLY

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "ساعت پایان باید بعد از شروع، در همان روز باشد."})
        return attrs


class StudentSerializer(ScopedSerializer):
    hall = serializers.PrimaryKeyRelatedField(queryset=Hall.objects.none())
    hall_name = serializers.CharField(source="hall.name", read_only=True)
    primary_phone = serializers.CharField(max_length=24)
    secondary_phone = serializers.CharField(max_length=24, allow_blank=True, required=False)

    class Meta:
        model = Student
        fields = [
            *COMMON,
            "identifier",
            "desk_number",
            "first_name",
            "last_name",
            "primary_phone",
            "secondary_phone",
            "grade",
            "major",
            "hall",
            "hall_name",
        ]
        read_only_fields = [*READONLY, "hall_name"]
        # Organization comes from the authenticated session; validate the scoped
        # uniqueness explicitly inside the organization's write transaction.
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization = self.context.get("organization")
        if organization:
            self.fields["hall"].queryset = Hall.objects.filter(organization=organization)

    def validate_identifier(self, value):
        value = digits(value).strip()
        exists = Student.objects.filter(organization=self.context["organization"], identifier=value)
        if self.instance:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise serializers.ValidationError(
                "این شناسه در مجموعه ثبت شده است؛ شناسهٔ بایگانی‌شده نیز محفوظ است."
            )
        return value

    def validate_desk_number(self, value):
        return digits(value).strip()

    def validate_primary_phone(self, value):
        return CustomerSerializer().validate_phone(value)

    def validate_secondary_phone(self, value):
        return self.validate_primary_phone(value) if value else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        hall = attrs.get("hall", getattr(self.instance, "hall", None))
        active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        hall_changed = "hall" in attrs and (self.instance is None or self.instance.hall_id != hall.pk)
        if hall and not hall.is_active and (active or hall_changed):
            raise serializers.ValidationError({"hall": "سالن انتخابی بایگانی شده است."})
        adding_active = active and (self.instance is None or not self.instance.is_active)
        if adding_active:
            organization = self.context["organization"]
            count = Student.objects.filter(organization=organization, is_active=True).count()
            if organization.capacity is None or count >= organization.capacity:
                raise serializers.ValidationError(
                    {
                        "detail": "ظرفیت فعال مجموعه تکمیل است؛ ابتدا ظرفیت را افزایش دهید یا دانش‌آموزی را بایگانی کنید."
                    }
                )
        return attrs


class AssignmentItem(serializers.Serializer):
    hall = serializers.IntegerField(min_value=1)
    session = serializers.IntegerField(min_value=1)


class AssignmentSerializer(serializers.Serializer):
    assignments = AssignmentItem(many=True)


class BulkStudentSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=200)
    action = serializers.ChoiceField(choices=["archive", "restore", "transfer"])
    hall = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if len(attrs["ids"]) != len(set(attrs["ids"])):
            raise serializers.ValidationError({"ids": "شناسه‌های تکراری مجاز نیستند."})
        if attrs["action"] == "transfer" and "hall" not in attrs:
            raise serializers.ValidationError({"hall": "سالن مقصد را انتخاب کنید."})
        return attrs
