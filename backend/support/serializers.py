from rest_framework import serializers

from core.models import Customer, User

from .models import Message, Notification, StatusEvent, Ticket


class StrictSerializer(serializers.Serializer):
    def validate(self, attrs):
        extras = set(self.initial_data) - set(self.fields)
        if extras:
            raise serializers.ValidationError({key: "این فیلد مجاز نیست." for key in extras})
        return attrs


class CreateTicketSerializer(StrictSerializer):
    subject = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=Ticket.Category.choices)
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices, default=Ticket.Priority.NORMAL)
    description = serializers.CharField(max_length=10000)


class ReplySerializer(StrictSerializer):
    body = serializers.CharField(max_length=10000)


class TransitionSerializer(StrictSerializer):
    action = serializers.ChoiceField(choices=["resolve", "close", "reopen"])


class AssignmentSerializer(StrictSerializer):
    assigned_to = serializers.IntegerField(min_value=1, allow_null=True)


class ReadNotificationsSerializer(StrictSerializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    ticket_id = serializers.IntegerField(min_value=1, required=False)
    include_messages = serializers.BooleanField(default=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if ("ids" in attrs) == ("ticket_id" in attrs):
            raise serializers.ValidationError("شناسه اعلان‌ها یا تیکت را مشخص کنید.")
        if "include_messages" in self.initial_data and "ticket_id" not in attrs:
            raise serializers.ValidationError(
                {"include_messages": "این گزینه فقط همراه شناسه تیکت مجاز است."}
            )
        return attrs


class OrganizationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "slug"]


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class StatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusEvent
        fields = ["id", "previous_status", "status", "actor_name", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    organization = OrganizationSummarySerializer(read_only=True)
    assigned_to = StaffSerializer(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    last_message_preview = serializers.SerializerMethodField()
    can_reply = serializers.SerializerMethodField()
    can_resolve = serializers.SerializerMethodField()
    can_close = serializers.SerializerMethodField()
    can_reopen = serializers.SerializerMethodField()
    can_assign = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "subject",
            "category",
            "priority",
            "status",
            "organization",
            "assigned_to",
            "created_at",
            "updated_at",
            "unread_count",
            "last_message_preview",
            "can_reply",
            "can_resolve",
            "can_close",
            "can_reopen",
            "can_assign",
        ]

    def get_last_message_preview(self, ticket):
        return (ticket.last_body or "")[:160]

    def get_can_reply(self, ticket):
        return ticket.status not in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}

    def get_can_resolve(self, ticket):
        return self.context["request"].user.role != User.Role.TENANT and self.get_can_reply(ticket)

    def get_can_close(self, ticket):
        return (
            self.context["request"].user.role == User.Role.TENANT and ticket.status == Ticket.Status.RESOLVED
        )

    def get_can_reopen(self, ticket):
        return self.context["request"].user.role == User.Role.TENANT and ticket.status in {
            Ticket.Status.RESOLVED,
            Ticket.Status.CLOSED,
        }

    def get_can_assign(self, ticket):
        return self.context["request"].user.role != User.Role.TENANT


class TicketDetailSerializer(TicketSerializer):
    status_history = serializers.SerializerMethodField()
    status_history_count = serializers.SerializerMethodField()

    class Meta(TicketSerializer.Meta):
        fields = [*TicketSerializer.Meta.fields, "status_history", "status_history_count"]

    def get_status_history(self, ticket):
        events = list(ticket.status_history.order_by("-created_at", "-pk")[:50])
        return StatusEventSerializer(reversed(events), many=True).data

    def get_status_history_count(self, ticket):
        return ticket.status_history.count()


class MessageSerializer(serializers.ModelSerializer):
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "body", "author_name", "author_role", "created_at", "is_mine"]

    def get_is_mine(self, message):
        return message.author_id == self.context["request"].user.pk


class NotificationSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="ticket.subject", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "ticket_id", "subject", "kind", "body", "created_at", "is_read"]

    def get_is_read(self, notification):
        return notification.read_at is not None
