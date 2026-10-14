from datetime import timedelta

import jdatetime
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import Hall, Supervisor
from operations.services import lock_organization
from operations.views import OrganizationViewSet
from portal.views import IsOrganizationUser, owned_organization
from staff.permissions import IsSupervisor, authorized_halls, current_supervisor

from .models import ScheduleAudit, WorkShift
from .serializers import (
    ApplySerializer,
    CopyPreviewSerializer,
    PreviewSerializer,
    ScheduleAssignmentSerializer,
    WorkShiftSerializer,
)
from .services import (
    apply_preview,
    assignment_query,
    build_preview,
    copy_preview,
    detect_conflicts,
    revision,
    validate_live_manager,
)


def week_dates(request):
    today = timezone.localdate()
    default = today - timedelta(days=(today.weekday() + 2) % 7)
    raw = request.query_params.get("week_start", str(default))
    from rest_framework.fields import DateField

    first = DateField().run_validation(raw)
    if first.weekday() != 5:
        raise ValidationError({"week_start": "هفته باید از شنبه آغاز شود."})
    return first, [first + timedelta(days=offset) for offset in range(7)]


def calendar_days(dates):
    return [
        {
            "date": date.isoformat(),
            "jalali_date": jdatetime.date.fromgregorian(date=date).isoformat(),
            "weekday": (date.weekday() + 2) % 7,
        }
        for date in dates
    ]


def filter_id(request, key):
    value = request.query_params.get(key)
    if not value:
        return None
    try:
        number = int(value)
        if number < 1:
            raise ValueError
        return number
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: "فیلتر انتخاب‌شده معتبر نیست."}) from exc


class WorkShiftViewSet(OrganizationViewSet):
    model = WorkShift
    serializer_class = WorkShiftSerializer

    def get_queryset(self):
        rows = WorkShift.objects.filter(organization=self.organization)
        if self.action == "list":
            selected = self.request.query_params.get("status", "active")
            if selected not in {"active", "archived", "all"}:
                raise ValidationError({"status": "وضعیت انتخاب‌شده معتبر نیست."})
            if selected != "all":
                rows = rows.filter(is_active=selected == "active")
            search = self.request.query_params.get("search", "").strip()
            if search:
                rows = rows.filter(name__icontains=search)
        return rows.order_by("start_time", "end_time", "pk")

    def perform_create(self, serializer):
        validate_live_manager(self.organization, self.request.user)
        shift = serializer.save(organization=self.organization)
        ScheduleAudit.objects.create(
            organization=self.organization,
            actor=self.request.user,
            action="create_shift",
            changes={"shift": WorkShiftSerializer(shift).data},
        )

    def perform_update(self, serializer):
        validate_live_manager(self.organization, self.request.user)
        before = dict(WorkShiftSerializer(serializer.instance).data)
        shift = serializer.save()
        ScheduleAudit.objects.create(
            organization=self.organization,
            actor=self.request.user,
            action="update_shift",
            changes={"before": before, "after": WorkShiftSerializer(shift).data},
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def restore(self, request, slug, pk=None):
        self._organization = lock_organization(request, slug)
        serializer = self.get_serializer(self.get_object(), data={"is_active": True}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class ScheduleView(APIView):
    permission_classes = [IsOrganizationUser]

    def get(self, request, slug):
        organization = owned_organization(request, slug)
        first, dates = week_dates(request)
        rows = assignment_query(organization).filter(date__in=dates)
        hall_id, shift_id = filter_id(request, "hall"), filter_id(request, "shift")
        if hall_id:
            if not Hall.objects.filter(pk=hall_id, organization=organization).exists():
                raise ValidationError({"hall": "سالن انتخاب‌شده در این مجموعه یافت نشد."})
            rows = rows.filter(hall_id=hall_id)
        if shift_id:
            if not WorkShift.objects.filter(pk=shift_id, organization=organization).exists():
                raise ValidationError({"shift": "شیفت انتخاب‌شده در این مجموعه یافت نشد."})
            rows = rows.filter(shift_id=shift_id)
        # Keep conflict details across halls even when the manager filters a hall.
        all_assignments = list(
            ScheduleAssignmentSerializer(
                assignment_query(organization).filter(date__in=dates), many=True
            ).data
        )
        return Response(
            {
                "week_start": str(first),
                "week_end": str(dates[-1]),
                "days": calendar_days(dates),
                "revision": revision(organization, dates),
                "assignments": ScheduleAssignmentSerializer(rows, many=True).data,
                "shifts": WorkShiftSerializer(
                    WorkShift.objects.filter(organization=organization, is_active=True), many=True
                ).data,
                "halls": list(
                    Hall.objects.filter(organization=organization, is_active=True).values("id", "name")
                ),
                "supervisors": [
                    {
                        "id": person.pk,
                        "first_name": person.first_name,
                        "last_name": person.last_name,
                        "halls": [hall.pk for hall in person.halls.all() if hall.is_active],
                    }
                    for person in Supervisor.objects.filter(
                        organization=organization, is_active=True, archived_at__isnull=True
                    ).prefetch_related("halls")
                ],
                "conflicts": detect_conflicts([], all_assignments, existing_only=True),
            }
        )


class SchedulePreviewView(APIView):
    permission_classes = [IsOrganizationUser]

    @transaction.atomic
    def post(self, request, slug):
        organization = lock_organization(request, slug)
        data = PreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            build_preview(
                organization,
                request.user,
                data.validated_data["assignments"],
                data.validated_data["remove_ids"],
            )
        )


class ScheduleCopyPreviewView(APIView):
    permission_classes = [IsOrganizationUser]

    @transaction.atomic
    def post(self, request, slug):
        organization = lock_organization(request, slug)
        data = CopyPreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(copy_preview(organization, request.user, data.validated_data))


class ScheduleApplyView(APIView):
    permission_classes = [IsOrganizationUser]

    def post(self, request, slug):
        organization = owned_organization(request, slug)
        data = ApplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(apply_preview(organization, request.user, data.validated_data))


class ScheduleAuditView(APIView):
    permission_classes = [IsOrganizationUser]

    def get(self, request, slug):
        organization = owned_organization(request, slug)
        rows = ScheduleAudit.objects.filter(organization=organization).select_related("actor")[:100]
        return Response(
            [
                {
                    "id": row.pk,
                    "actor": row.actor.get_full_name() or row.actor.portal_username,
                    "action": row.action,
                    "reason": row.reason,
                    "changes": row.changes,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        )


class SupervisorScheduleView(APIView):
    permission_classes = [IsSupervisor]

    def get(self, request, slug):
        account = current_supervisor(request, slug)
        first, dates = week_dates(request)
        halls = authorized_halls(account)
        hall_id = filter_id(request, "hall")
        if hall_id and not halls.filter(pk=hall_id).exists():
            raise ValidationError({"hall": "به سالن انتخاب‌شده دسترسی ندارید."})
        rows = assignment_query(account.organization).filter(
            supervisor_id=account.supervisor_id, hall__in=halls, date__in=dates
        )
        if hall_id:
            rows = rows.filter(hall_id=hall_id)
        serialized = list(ScheduleAssignmentSerializer(rows, many=True).data)
        return Response(
            {
                "week_start": str(first),
                "week_end": str(dates[-1]),
                "days": calendar_days(dates),
                "assignments": serialized,
                "halls": list(halls.values("id", "name")),
                "shifts": WorkShiftSerializer(
                    WorkShift.objects.filter(
                        organization=account.organization, assignments__in=rows
                    ).distinct(),
                    many=True,
                ).data,
                "conflicts": detect_conflicts([], serialized, existing_only=True),
            }
        )
