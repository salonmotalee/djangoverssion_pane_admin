from rest_framework import serializers

from .models import AttendanceRecord, PresenceEvent


class PresencePayload(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=PresenceEvent.Kind.values)


class AttendanceSelection(serializers.Serializer):
    hall = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    session = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class DecisionItem(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=AttendanceRecord.Status.values)
    revision = serializers.IntegerField(min_value=1, required=False)


class ManualPayload(AttendanceSelection):
    session = serializers.IntegerField(min_value=1)
    records = DecisionItem(many=True, allow_empty=False, max_length=500)

    def validate_records(self, value):
        if len({item["student"] for item in value}) != len(value):
            raise serializers.ValidationError("دانش‌آموز تکراری در یک درخواست مجاز نیست.")
        return value


class AutomaticPayload(serializers.Serializer):
    preview_token = serializers.CharField(max_length=8000)
    students = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=500
    )

    def validate_students(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("دانش‌آموز تکراری مجاز نیست.")
        return value


class CorrectionItem(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=AttendanceRecord.Status.values)
    revision = serializers.IntegerField(min_value=1)


class CorrectionPayload(serializers.Serializer):
    records = CorrectionItem(many=True, allow_empty=False, max_length=500)
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)

    def validate_records(self, value):
        if len({item["id"] for item in value}) != len(value):
            raise serializers.ValidationError("رکورد تکراری مجاز نیست.")
        return value
