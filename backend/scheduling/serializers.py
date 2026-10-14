from rest_framework import serializers

from .models import ScheduleAssignment, WorkShift


class WorkShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkShift
        fields = ["id", "name", "start_time", "end_time", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_time", self.instance.start_time if self.instance else None)
        end = attrs.get("end_time", self.instance.end_time if self.instance else None)
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "پایان شیفت باید بعد از شروع، در همان روز باشد."})
        return attrs


class ScheduleAssignmentSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source="hall.name", read_only=True)
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleAssignment
        fields = [
            "id",
            "date",
            "hall",
            "hall_name",
            "shift",
            "shift_name",
            "supervisor",
            "supervisor_name",
            "start_time",
            "end_time",
            "conflict_override",
            "override_reason",
            "created_at",
        ]

    def get_supervisor_name(self, obj):
        return f"{obj.supervisor.first_name} {obj.supervisor.last_name}"


class ProposalRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    hall = serializers.IntegerField(min_value=1)
    shift = serializers.IntegerField(min_value=1)
    supervisor = serializers.IntegerField(min_value=1)


class PreviewSerializer(serializers.Serializer):
    assignments = ProposalRowSerializer(many=True, max_length=5000)
    remove_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=5000, default=list
    )


class ActionSerializer(serializers.Serializer):
    index = serializers.IntegerField(min_value=0)
    action = serializers.ChoiceField(choices=["add", "preserve", "replace", "skip"])
    replace_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=5000, default=list
    )


class ApplySerializer(serializers.Serializer):
    token = serializers.CharField(max_length=300000)
    actions = ActionSerializer(many=True, max_length=5000)
    remove_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=5000, default=list
    )
    confirm_conflicts = serializers.BooleanField(default=False)
    override_reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class CopyPreviewSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["week", "month"])
    source_week = serializers.DateField()
    target_week = serializers.DateField(required=False)
    jalali_year = serializers.IntegerField(min_value=1300, max_value=1600, required=False)
    jalali_month = serializers.IntegerField(min_value=1, max_value=12, required=False)

    def validate(self, attrs):
        if attrs["source_week"].weekday() != 5:
            raise serializers.ValidationError({"source_week": "هفته باید از شنبه آغاز شود."})
        if attrs["mode"] == "week":
            if "target_week" not in attrs or attrs["target_week"].weekday() != 5:
                raise serializers.ValidationError({"target_week": "شنبهٔ هفته مقصد را انتخاب کنید."})
            if attrs["source_week"] == attrs["target_week"]:
                raise serializers.ValidationError({"target_week": "هفتهٔ مبدأ و مقصد باید متفاوت باشند."})
        elif "jalali_year" not in attrs or "jalali_month" not in attrs:
            raise serializers.ValidationError("سال و ماه شمسی مقصد الزامی است.")
        return attrs
