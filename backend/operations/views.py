from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from portal.views import IsOrganizationUser, owned_organization

from .models import Hall, HallSession, Student, StudySession
from .serializers import (
    AssignmentSerializer,
    BulkStudentSerializer,
    HallSerializer,
    StudentSerializer,
    StudySessionSerializer,
    digits,
)
from .services import lock_organization


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationUser]
    model = None
    ordering_fields = {"name", "created_at"}

    @property
    def organization(self):
        if not hasattr(self, "_organization"):
            self._organization = owned_organization(self.request, self.kwargs["slug"])
        return self._organization

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "organization": self.organization}

    def get_queryset(self):
        queryset = self.model.objects.filter(organization=self.organization)
        if self.model is Hall:
            queryset = queryset.annotate(
                active_students=Count("students", filter=Q(students__is_active=True))
            )
        if self.model is Student:
            queryset = queryset.select_related("hall")
        if self.action != "list":
            return queryset
        params = self.request.query_params
        active = params.get("status", "active")
        if active not in {"active", "archived", "all"}:
            raise ValidationError({"status": "وضعیت انتخاب‌شده معتبر نیست."})
        if active != "all":
            queryset = queryset.filter(is_active=active == "active")
        search = digits(params.get("search", "").strip())
        if search:
            fields = (
                ["identifier", "first_name", "last_name", "primary_phone", "secondary_phone", "desk_number"]
                if self.model is Student
                else ["name"]
                if self.model is Hall
                else ["title"]
            )
            query = Q()
            for field in fields:
                query |= Q(**{field + "__icontains": search})
            if self.model is Student and len(search.split()) > 1:
                query |= Q(
                    first_name__icontains=search.split()[0], last_name__icontains=" ".join(search.split()[1:])
                )
            queryset = queryset.filter(query)
        if self.model is Student:
            for key in ["hall", "grade", "major"]:
                value = params.get(key)
                if not value:
                    continue
                if key in {"hall", "grade"}:
                    try:
                        value = int(value)
                    except ValueError as exc:
                        raise ValidationError({key: "مقدار فیلتر معتبر نیست."}) from exc
                if (
                    key == "hall"
                    and not Hall.objects.filter(pk=value, organization=self.organization).exists()
                ):
                    raise ValidationError({key: "سالن انتخابی معتبر نیست."})
                if key == "grade" and value not in Student.Grade.values:
                    raise ValidationError({key: "پایهٔ انتخابی معتبر نیست."})
                if key == "major" and value not in Student.Major.values:
                    raise ValidationError({key: "رشتهٔ انتخابی معتبر نیست."})
                queryset = queryset.filter(**{key + "_id" if key == "hall" else key: value})
        if self.model is StudySession:
            # Client ordering never overrides the chronological business rule.
            return queryset.order_by("start_time", "end_time", "pk")
        ordering = params.get("ordering", "-created_at" if self.model is Student else "name")
        if ordering.removeprefix("-") not in self.ordering_fields:
            raise ValidationError({"ordering": "مرتب‌سازی انتخاب‌شده معتبر نیست."})
        return queryset.order_by(ordering, "pk")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self._organization = lock_organization(request, kwargs["slug"])
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self._organization = lock_organization(request, kwargs["slug"])
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(organization=self.organization)

    def perform_update(self, serializer):
        instance = serializer.save()
        if not instance.is_active:
            if isinstance(instance, Hall):
                instance.session_assignments.all().delete()
            elif isinstance(instance, StudySession):
                instance.hall_assignments.all().delete()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        self._organization = lock_organization(request, kwargs["slug"])
        serializer = self.get_serializer(self.get_object(), data={"is_active": False}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def restore(self, request, slug, pk=None):
        self._organization = lock_organization(request, slug)
        serializer = self.get_serializer(self.get_object(), data={"is_active": True}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class HallViewSet(OrganizationViewSet):
    model = Hall
    serializer_class = HallSerializer

    @action(detail=False, methods=["get"])
    def options(self, request, slug):
        return Response(self.get_serializer(self.get_queryset().filter(is_active=True), many=True).data)


class StudySessionViewSet(OrganizationViewSet):
    model = StudySession
    serializer_class = StudySessionSerializer


class StudentViewSet(OrganizationViewSet):
    model = Student
    serializer_class = StudentSerializer
    ordering_fields = {
        "identifier",
        "first_name",
        "last_name",
        "desk_number",
        "grade",
        "created_at",
        "updated_at",
    }

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def bulk(self, request, slug):
        self._organization = lock_organization(request, slug)
        payload = BulkStudentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        students = list(self.get_queryset().filter(pk__in=data["ids"]).order_by("pk"))
        if len(students) != len(data["ids"]):
            raise ValidationError({"ids": "یک یا چند دانش‌آموز در این مجموعه یافت نشد."})
        changes = (
            {"hall": data["hall"]}
            if data["action"] == "transfer"
            else {"is_active": data["action"] == "restore"}
        )
        for student in students:
            serializer = self.get_serializer(student, data=changes, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response({"updated": len(students)})


class AssignmentsView(APIView):
    permission_classes = [IsOrganizationUser]

    def snapshot(self, organization):
        halls = Hall.objects.filter(organization=organization, is_active=True).annotate(
            active_students=Count("students", filter=Q(students__is_active=True))
        )
        sessions = StudySession.objects.filter(organization=organization, is_active=True)
        return {
            "halls": HallSerializer(halls, many=True).data,
            "sessions": StudySessionSerializer(sessions, many=True).data,
            "assignments": list(
                HallSession.objects.filter(hall__in=halls, session__in=sessions).values("hall", "session")
            ),
        }

    def get(self, request, slug):
        return Response(self.snapshot(owned_organization(request, slug)))

    @transaction.atomic
    def put(self, request, slug):
        organization = lock_organization(request, slug)
        payload = AssignmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        pairs = [(item["hall"], item["session"]) for item in payload.validated_data["assignments"]]
        if len(set(pairs)) != len(pairs):
            raise ValidationError({"assignments": "تخصیص تکراری مجاز نیست."})
        hall_ids = set(
            Hall.objects.filter(organization=organization, is_active=True).values_list("pk", flat=True)
        )
        session_ids = set(
            StudySession.objects.filter(organization=organization, is_active=True).values_list(
                "pk", flat=True
            )
        )
        if any(hall not in hall_ids or session not in session_ids for hall, session in pairs):
            raise ValidationError(
                {"assignments": "سالن یا پارت نامعتبر، متعلق به مجموعهٔ دیگر یا بایگانی‌شده است."}
            )
        HallSession.objects.filter(hall__organization=organization).delete()
        # All rows were scoped and validated above while holding the organization lock.
        HallSession.objects.bulk_create(
            [HallSession(hall_id=hall, session_id=session) for hall, session in pairs]
        )
        return Response(self.snapshot(organization))
