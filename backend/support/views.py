from django.db import transaction
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Customer, User
from core.views import date_range

from .models import Message, Notification, Ticket
from .permissions import CanUseSupport, support_staff
from .serializers import (
    AssignmentSerializer,
    CreateTicketSerializer,
    MessageSerializer,
    NotificationSerializer,
    ReadNotificationsSerializer,
    ReplySerializer,
    StaffSerializer,
    StatusEventSerializer,
    TicketDetailSerializer,
    TicketSerializer,
    TransitionSerializer,
)
from .services import add_message, audit, set_status


def visible_tickets(request):
    queryset = Ticket.objects.all()
    if request.user.role == User.Role.TENANT:
        queryset = queryset.filter(organization_id=request.user.organization_id)
    return queryset


def visible_notifications(request):
    return Notification.objects.filter(
        recipient=request.user,
        ticket__in=visible_tickets(request).order_by().values("pk"),
    )


class TicketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [CanUseSupport]
    serializer_class = TicketSerializer

    def get_queryset(self):
        last_message = Message.objects.filter(ticket=OuterRef("pk")).order_by("-created_at", "-pk")
        queryset = (
            visible_tickets(self.request)
            .select_related("organization", "assigned_to")
            .annotate(
                unread_count=Count(
                    "notifications",
                    filter=Q(
                        notifications__recipient=self.request.user,
                        notifications__read_at__isnull=True,
                        notifications__kind=Notification.Kind.MESSAGE,
                    ),
                ),
                last_body=Subquery(last_message.values("body")[:1]),
            )
            .order_by("-updated_at", "-pk")
        )
        if self.action != "list":
            return queryset
        params = self.request.query_params
        search = params.get("search", "").strip()
        if len(search) > 200:
            raise ValidationError({"search": "عبارت جست‌وجو بیش از حد طولانی است."})
        if search:
            condition = (
                Q(subject__icontains=search)
                | Q(organization__name__icontains=search)
                | Q(matching_message=True)
            )
            ticket_number = (
                search.lstrip("#")
                .strip()
                .translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            )
            if ticket_number.isdecimal() and 0 < int(ticket_number) <= 9223372036854775807:
                condition |= Q(pk=int(ticket_number))
            queryset = queryset.alias(
                matching_message=Exists(Message.objects.filter(ticket=OuterRef("pk"), body__icontains=search))
            ).filter(condition)
        for field, choices in [("status", Ticket.Status.values), ("priority", Ticket.Priority.values)]:
            value = params.get(field)
            if value:
                if value not in choices:
                    raise ValidationError({field: "مقدار فیلتر معتبر نیست."})
                queryset = queryset.filter(**{field: value})
        for field in ["unread", "unanswered"]:
            if field not in params:
                continue
            value = params[field]
            if value not in {"true", "false"}:
                raise ValidationError({field: "مقدار باید true یا false باشد."})
            if field == "unread":
                queryset = (
                    queryset.filter(unread_count__gt=0)
                    if value == "true"
                    else queryset.filter(unread_count=0)
                )
            else:
                condition = Q(status__in=[Ticket.Status.OPEN, Ticket.Status.AWAITING_SUPPORT])
                queryset = queryset.filter(condition) if value == "true" else queryset.exclude(condition)
        organization = params.get("organization", "").strip()
        if organization:
            if organization.isdigit():
                queryset = queryset.filter(organization_id=int(organization))
            else:
                queryset = queryset.filter(organization__slug=organization)
        lower, upper = date_range(params, "date_from", "date_to")
        if lower:
            queryset = queryset.filter(created_at__date__gte=lower)
        if upper:
            queryset = queryset.filter(created_at__date__lte=upper)
        return queryset

    def get_serializer_class(self):
        return TicketDetailSerializer if self.action == "retrieve" else TicketSerializer

    def fresh_ticket(self, ticket):
        return self.get_queryset().get(pk=ticket.pk)

    def lock_actor(self):
        # Match portal mutations' organization-before-owner lock ordering.
        if self.request.user.role == User.Role.TENANT:
            Customer.objects.select_for_update().get(pk=self.request.user.organization_id)
        # NO KEY UPDATE still serializes permission changes while allowing FK
        # references from concurrent notification and audit writers on PostgreSQL.
        current = User.objects.select_for_update(no_key=True).get(pk=self.request.user.pk)
        self.request.user = current
        self.check_permissions(self.request)

    def locked_ticket(self):
        self.lock_actor()
        return get_object_or_404(visible_tickets(self.request).select_for_update(), pk=self.kwargs["pk"])

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("ایجاد تیکت از پرتال مجموعه انجام می‌شود.")
        self.lock_actor()
        payload = CreateTicketSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        fields = dict(payload.validated_data)
        body = fields.pop("description")
        ticket = Ticket.objects.create(
            organization_id=request.user.organization_id, created_by=request.user, **fields
        )
        set_status(ticket, request.user, Ticket.Status.OPEN, initial=True)
        add_message(ticket, request.user, body)
        return Response(self.get_serializer(self.fresh_ticket(ticket)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def messages(self, request, *args, **kwargs):
        if request.method == "GET":
            ticket = self.get_object()
            ordering = request.query_params.get("ordering", "created_at")
            if ordering not in {"created_at", "-created_at"}:
                raise ValidationError({"ordering": "مرتب‌سازی انتخاب‌شده معتبر نیست."})
            queryset = ticket.messages.order_by(ordering, "-pk" if ordering.startswith("-") else "pk")
            page = self.paginate_queryset(queryset)
            messages = page if page is not None else list(queryset)
            visible_notifications(request).filter(
                message_id__in=[message.pk for message in messages], read_at__isnull=True
            ).update(read_at=timezone.now())
            serialized = MessageSerializer(messages, many=True, context={"request": request}).data
            return self.get_paginated_response(serialized) if page is not None else Response(serialized)
        payload = ReplySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            ticket = self.locked_ticket()
            if ticket.status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
                raise ValidationError({"detail": "برای ارسال پیام، ابتدا مجموعه باید تیکت را بازگشایی کند."})
            message = add_message(ticket, request.user, payload.validated_data["body"])
            set_status(
                ticket,
                request.user,
                Ticket.Status.AWAITING_SUPPORT
                if request.user.role == User.Role.TENANT
                else Ticket.Status.AWAITING_CUSTOMER,
            )
            audit(ticket, request.user, "support_reply", "ارسال پیام پشتیبانی", {"message_id": message.pk})
        return Response(MessageSerializer(message, context={"request": request}).data, status=201)

    @action(detail=True, methods=["get"])
    def history(self, request, *args, **kwargs):
        ticket = self.get_object()
        queryset = ticket.status_history.order_by("-created_at", "-pk")
        page = self.paginate_queryset(queryset)
        events = page if page is not None else queryset
        data = StatusEventSerializer(events, many=True).data
        return self.get_paginated_response(data) if page is not None else Response(data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transition(self, request, *args, **kwargs):
        payload = TransitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        ticket = self.locked_ticket()
        action_name = payload.validated_data["action"]
        tenant = request.user.role == User.Role.TENANT
        if action_name == "resolve":
            if tenant:
                raise PermissionDenied("حل تیکت فقط توسط پشتیبانی انجام می‌شود.")
            allowed = ticket.status not in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}
            target = Ticket.Status.RESOLVED
        elif action_name == "close":
            if not tenant:
                raise PermissionDenied("تأیید و بستن تیکت فقط توسط مجموعه انجام می‌شود.")
            allowed = ticket.status == Ticket.Status.RESOLVED
            target = Ticket.Status.CLOSED
        else:
            if not tenant:
                raise PermissionDenied("بازگشایی تیکت فقط توسط مجموعه انجام می‌شود.")
            allowed = ticket.status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}
            target = Ticket.Status.AWAITING_SUPPORT
        if not allowed:
            raise ValidationError({"action": "این تغییر در وضعیت فعلی تیکت مجاز نیست."})
        set_status(ticket, request.user, target)
        return Response(self.get_serializer(self.fresh_ticket(ticket)).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def assign(self, request, *args, **kwargs):
        if request.user.role == User.Role.TENANT:
            raise PermissionDenied("ارجاع تیکت فقط توسط پشتیبانی انجام می‌شود.")
        payload = AssignmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        ticket = self.locked_ticket()
        assigned_id = payload.validated_data["assigned_to"]
        assigned = None
        if assigned_id is not None:
            assigned = support_staff().filter(pk=assigned_id).first()
            if assigned is None:
                raise ValidationError({"assigned_to": "کاربر انتخاب‌شده دسترسی فعال پشتیبانی ندارد."})
        previous = ticket.assigned_to_id
        if previous != assigned_id:
            ticket.assigned_to = assigned
            ticket.save(update_fields=["assigned_to", "updated_at"])
            audit(
                ticket,
                request.user,
                "support_assign",
                "ارجاع تیکت پشتیبانی",
                {"assigned_to": {"before": previous, "after": assigned_id}},
            )
            if assigned is not None and assigned.pk != request.user.pk:
                Notification.objects.create(
                    recipient=assigned,
                    ticket=ticket,
                    kind="assignment",
                    body="این تیکت برای رسیدگی به شما ارجاع شد.",
                )
        return Response(self.get_serializer(self.fresh_ticket(ticket)).data)


class StaffView(APIView):
    permission_classes = [CanUseSupport]

    def get(self, request, **kwargs):
        if request.user.role == User.Role.TENANT:
            raise PermissionDenied("فهرست کارکنان ویژه پشتیبانی مرکزی است.")
        return Response(
            StaffSerializer(support_staff().order_by("first_name", "last_name", "username"), many=True).data
        )


class NotificationsView(APIView):
    permission_classes = [CanUseSupport]

    def get(self, request, **kwargs):
        notifications = visible_notifications(request)
        counts = notifications.aggregate(
            unread_count=Count("pk", filter=Q(read_at__isnull=True)),
            unread_messages=Count("pk", filter=Q(read_at__isnull=True, kind=Notification.Kind.MESSAGE)),
        )
        ticket_counts = visible_tickets(request).aggregate(
            open_tickets=Count(
                "pk",
                filter=Q(
                    status__in=[
                        Ticket.Status.OPEN,
                        Ticket.Status.AWAITING_SUPPORT,
                        Ticket.Status.AWAITING_CUSTOMER,
                    ]
                ),
            ),
            awaiting_support=Count(
                "pk", filter=Q(status__in=[Ticket.Status.OPEN, Ticket.Status.AWAITING_SUPPORT])
            ),
            awaiting_customer=Count("pk", filter=Q(status=Ticket.Status.AWAITING_CUSTOMER)),
        )
        return Response(
            {
                **counts,
                **ticket_counts,
                "items": NotificationSerializer(
                    notifications.select_related("ticket")
                    .alias(
                        read_order=Case(
                            When(read_at__isnull=True, then=Value(0)),
                            default=Value(1),
                            output_field=IntegerField(),
                        )
                    )
                    .order_by("read_order", "-created_at", "-pk")[:20],
                    many=True,
                ).data,
            }
        )


class ReadNotificationsView(APIView):
    permission_classes = [CanUseSupport]

    def post(self, request, **kwargs):
        payload = ReadNotificationsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        notifications = visible_notifications(request).filter(read_at__isnull=True)
        if "ticket_id" in payload.validated_data:
            ticket_id = payload.validated_data["ticket_id"]
            get_object_or_404(visible_tickets(request), pk=ticket_id)
            notifications = notifications.filter(ticket_id=ticket_id)
            if not payload.validated_data["include_messages"]:
                notifications = notifications.exclude(kind=Notification.Kind.MESSAGE)
        else:
            notifications = notifications.filter(pk__in=payload.validated_data["ids"])
        return Response({"updated": notifications.update(read_at=timezone.now())})
