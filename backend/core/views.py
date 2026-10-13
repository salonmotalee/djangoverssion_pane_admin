"""Session authenticated APIs for the custom Next.js administration interface."""

import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, Customer, User
from .permissions import IsAdministrator, IsInternalUser
from .serializers import (
    AuditSerializer,
    CustomerSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    RenewalSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from .services import (
    CUSTOMER_FIELDS,
    USER_FIELDS,
    failed_login,
    lock_and_guard_user,
    login_is_limited,
    record_audit,
    snapshot,
    successful_login,
    throttle_keys,
    throttle_records,
)


def csrf_failure(request, reason=""):
    return JsonResponse({"detail": "اعتبار درخواست منقضی شده است. صفحه را تازه‌سازی کنید."}, status=403)


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        credentials = LoginSerializer(data=request.data)
        credentials.is_valid(raise_exception=True)
        keys = throttle_keys(request, credentials.validated_data["username"])
        with transaction.atomic():
            counters = throttle_records(keys)
            if login_is_limited(counters):
                return Response(
                    {"detail": "تلاش‌های ورود بیش از حد مجاز است. ۱۵ دقیقه بعد دوباره تلاش کنید."},
                    status=429,
                    headers={"Retry-After": "900"},
                )
            authenticated = authenticate(request=request, **credentials.validated_data)
            user = None
            if authenticated is not None:
                # A concurrent reset/deactivation/removal invalidates credentials
                # checked earlier. Lock the current account before session creation.
                user = (
                    User.objects.select_for_update()
                    .filter(pk=authenticated.pk, is_active=True, password=authenticated.password)
                    .first()
                )
            if user is None:
                failed_login(counters)
                return Response({"detail": "نام کاربری یا رمز عبور صحیح نیست."}, status=400)
            successful_login(counters, keys[0][0])
            login(request, user, backend="core.authentication.InternalBackend")
            record_audit(user, "login", user, "ورود به سامانه")
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        record_audit(request.user, "logout", request.user, "خروج از سامانه")
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                raise PermissionDenied("حساب کاربری غیرفعال است.")
            serializer = ProfileSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            before = snapshot(user, USER_FIELDS)
            user = serializer.save()
            record_audit(user, "update_profile", user, "ویرایش پروفایل", before, USER_FIELDS)
        return Response(UserSerializer(user).data)


class PasswordView(APIView):
    def post(self, request):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                raise PermissionDenied("حساب کاربری غیرفعال است.")
            request.user = user
            serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])
            update_session_auth_hash(request, user)
            record_audit(user, "change_password", user, "تغییر رمز عبور شخصی")
        return Response({"detail": "رمز عبور با موفقیت تغییر کرد."})


def date_range(params, lower_name, upper_name):
    field = serializers.DateField()
    lower = upper = None
    for name in (lower_name, upper_name):
        raw = params.get(name)
        if raw:
            try:
                value = field.run_validation(raw)
            except ValidationError as exc:
                raise ValidationError({name: exc.detail}) from exc
            if name == lower_name:
                lower = value
            else:
                upper = value
    if lower and upper and lower > upper:
        raise ValidationError({upper_name: "تاریخ پایان بازه باید بعد از شروع آن باشد."})
    return lower, upper


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]
    queryset = (
        User.objects.filter(organization__isnull=True)
        .exclude(role=User.Role.TENANT)
        .order_by("-date_joined", "-pk")
    )
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )
        role = self.request.query_params.get("role")
        if role:
            if role not in User.Role.values:
                raise ValidationError({"role": "نقش معتبر نیست."})
            queryset = queryset.filter(role=role)
        active = self.request.query_params.get("is_active")
        if active:
            if active not in {"true", "false"}:
                raise ValidationError({"is_active": "مقدار باید true یا false باشد."})
            queryset = queryset.filter(is_active=active == "true")
        return queryset

    def ensure_manageable(self, user):
        if self.request.user.role == User.Role.ADMIN and user.role != User.Role.OPERATOR:
            raise PermissionDenied("مدیر فقط می‌تواند اپراتورها را مدیریت کند.")

    def retrieve(self, request, *args, **kwargs):
        self.ensure_manageable(self.get_object())
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        with transaction.atomic():
            user = serializer.save()
            record_audit(
                self.request.user, "create_user", user, f"ایجاد کاربر {user.username}", fields=USER_FIELDS
            )

    def perform_update(self, serializer):
        self.ensure_manageable(serializer.instance)
        with transaction.atomic():
            user = lock_and_guard_user(
                serializer.instance,
                serializer.validated_data.get("role"),
                serializer.validated_data.get("is_active"),
            )
            self.ensure_manageable(user)
            serializer.instance = user
            before = snapshot(user, USER_FIELDS)
            user = serializer.save()
            record_audit(
                self.request.user, "update_user", user, f"ویرایش کاربر {user.username}", before, USER_FIELDS
            )

    def perform_destroy(self, instance):
        self.ensure_manageable(instance)
        with transaction.atomic():
            user = lock_and_guard_user(instance, deleting=True)
            self.ensure_manageable(user)
            record_audit(
                self.request.user, "delete_user", user, f"حذف کاربر {user.username}", fields=USER_FIELDS
            )
            user.delete()

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        self.ensure_manageable(user)
        serializer = ResetPasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            self.ensure_manageable(user)
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])
            # Updating one's own password through administration retains only this session.
            if user.pk == request.user.pk:
                update_session_auth_hash(request, user)
            record_audit(request.user, "reset_password", user, f"بازنشانی رمز کاربر {user.username}")
        return Response({"detail": "رمز عبور کاربر بازنشانی شد."})


def status_filter(queryset, value, today=None):
    today = today or timezone.localdate()
    cutoff = today + timedelta(days=30)
    if value == "scheduled":
        return queryset.filter(start_date__gt=today)
    if value == "expired":
        return queryset.filter(start_date__lte=today, expiration_date__lt=today)
    if value == "expiring":
        return queryset.filter(start_date__lte=today, expiration_date__range=(today, cutoff))
    if value == "active":
        return queryset.filter(start_date__lte=today, expiration_date__gt=cutoff)
    if value == "current":
        # Query-only aggregate matching the dashboard's active_services metric.
        return queryset.filter(start_date__lte=today, expiration_date__gte=today)
    raise ValidationError({"status": "وضعیت انتخاب‌شده معتبر نیست."})


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsInternalUser]
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"destroy", "restore", "export", "portal"}:
            return [IsAdministrator()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Customer.objects.prefetch_related("portal_accounts").all()
        params = self.request.query_params
        deleted = params.get("deleted", "all" if self.action == "restore" else "active")
        if deleted == "active":
            queryset = queryset.filter(deleted_at__isnull=True)
        elif deleted == "deleted":
            queryset = queryset.filter(deleted_at__isnull=False)
        elif deleted != "all":
            raise ValidationError({"deleted": "فیلتر حذف معتبر نیست."})
        search = params.get("search", "").strip()
        if search:
            phone_search = search.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            phone_search = phone_search.replace(" ", "").replace("-", "")
            if phone_search.startswith("+98"):
                phone_search = "0" + phone_search[3:]
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(manager_name__icontains=search)
                | Q(phone__icontains=phone_search)
                | Q(identifier__icontains=search)
            )
        if params.get("status"):
            queryset = status_filter(queryset, params["status"])
        for field in ("start_date", "expiration_date"):
            lower, upper = date_range(params, field + "_from", field + "_to")
            if lower:
                queryset = queryset.filter(**{field + "__gte": lower})
            if upper:
                queryset = queryset.filter(**{field + "__lte": upper})
        lower, upper = date_range(params, "created_date_from", "created_date_to")
        if lower:
            queryset = queryset.filter(created_at__date__gte=lower)
        if upper:
            queryset = queryset.filter(created_at__date__lte=upper)
        ordering = params.get("ordering", "-created_at")
        fields = ordering.split(",")
        allowed = {
            "name",
            "manager_name",
            "identifier",
            "start_date",
            "expiration_date",
            "created_at",
            "updated_at",
        }
        if any(field.removeprefix("-") not in allowed for field in fields):
            raise ValidationError({"ordering": "مرتب‌سازی انتخاب‌شده معتبر نیست."})
        return queryset.order_by(*fields, "-pk")

    def perform_create(self, serializer):
        with transaction.atomic():
            customer = serializer.save()
            record_audit(
                self.request.user,
                "create_customer",
                customer,
                f"ایجاد مشتری {customer.name}",
                fields=CUSTOMER_FIELDS,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            customer = Customer.objects.select_for_update().get(pk=serializer.instance.pk)
            if customer.deleted_at:
                raise ValidationError("ابتدا مشتری حذف‌شده را بازیابی کنید.")
            serializer.instance = customer
            # Validate again against current dates/identifier after acquiring the lock.
            serializer.validate(serializer.validated_data)
            before = snapshot(customer, CUSTOMER_FIELDS)
            customer = serializer.save()
            record_audit(
                self.request.user,
                "update_customer",
                customer,
                f"ویرایش مشتری {customer.name}",
                before,
                CUSTOMER_FIELDS,
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            customer = Customer.objects.select_for_update().get(pk=instance.pk)
            if customer.deleted_at:
                raise ValidationError("این مشتری قبلاً حذف شده است.")
            before = snapshot(customer, CUSTOMER_FIELDS)
            customer.deleted_at = timezone.now()
            customer.save(update_fields=["deleted_at", "updated_at"])
            from django.db.models import F

            User.objects.filter(organization=customer).update(
                portal_session_version=F("portal_session_version") + 1
            )
            record_audit(
                self.request.user,
                "delete_customer",
                customer,
                f"حذف نرم مشتری {customer.name}",
                before,
                CUSTOMER_FIELDS,
            )

    @action(detail=True, methods=["post"])
    def portal(self, request, pk=None):
        from portal.serializers import PortalCredentialsSerializer
        from portal.services import provision_portal

        customer = self.get_object()
        serializer = PortalCredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provision_portal(customer, serializer.validated_data, request.user)
        fresh = Customer.objects.prefetch_related("portal_accounts").get(pk=customer.pk)
        return Response(CustomerSerializer(fresh, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        instance = self.get_object()
        with transaction.atomic():
            customer = Customer.objects.select_for_update().get(pk=instance.pk)
            if customer.deleted_at is None:
                raise ValidationError("این مشتری حذف نشده است.")
            before = snapshot(customer, CUSTOMER_FIELDS)
            customer.deleted_at = None
            customer.save(update_fields=["deleted_at", "updated_at"])
            record_audit(
                request.user,
                "restore_customer",
                customer,
                f"بازیابی مشتری {customer.name}",
                before,
                CUSTOMER_FIELDS,
            )
        return Response(CustomerSerializer(customer).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        instance = self.get_object()
        with transaction.atomic():
            customer = Customer.objects.select_for_update().get(pk=instance.pk)
            if customer.deleted_at:
                raise ValidationError("مشتری حذف‌شده قابل تمدید نیست.")
            serializer = RenewalSerializer(data=request.data, context={"customer": customer})
            serializer.is_valid(raise_exception=True)
            before = snapshot(customer, CUSTOMER_FIELDS)
            customer.expiration_date = serializer.validated_data["expiration_date"]
            customer.save(update_fields=["expiration_date", "updated_at"])
            record_audit(
                request.user,
                "renew_customer",
                customer,
                f"تمدید خدمت مشتری {customer.name}",
                before,
                CUSTOMER_FIELDS,
            )
        return Response(CustomerSerializer(customer).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        def safe_cell(value):
            text = str(value)
            if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
                return "'" + text
            return text

        output = StringIO(newline="")
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(
            ["نام مجموعه", "نام مدیر", "شماره همراه", "شناسه مشتری", "تاریخ شروع", "تاریخ پایان", "وضعیت"]
        )
        labels = {
            "active": "فعال",
            "scheduled": "زمان‌بندی‌شده",
            "expiring": "نزدیک به انقضا",
            "expired": "منقضی",
        }
        for item in self.get_queryset().iterator(chunk_size=500):
            writer.writerow(
                [
                    safe_cell(value)
                    for value in (
                        item.name,
                        item.manager_name,
                        item.phone,
                        item.identifier,
                        item.start_date.isoformat(),
                        item.expiration_date.isoformat(),
                        labels[item.status],
                    )
                ]
            )
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="customers.csv"'
        response["Cache-Control"] = "no-store"
        return response


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdministrator]
    serializer_class = AuditSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor")
        params = self.request.query_params
        for field in ("entity_type", "entity_id", "action"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) | Q(actor__username__icontains=search)
            )
        lower, upper = date_range(params, "date_from", "date_to")
        if lower:
            queryset = queryset.filter(created_at__date__gte=lower)
        if upper:
            queryset = queryset.filter(created_at__date__lte=upper)
        return queryset


class DashboardView(APIView):
    def get(self, request):
        today = timezone.localdate()
        queryset = Customer.objects.filter(deleted_at__isnull=True)
        lower, upper = date_range(request.query_params, "date_from", "date_to")
        if lower:
            queryset = queryset.filter(created_at__date__gte=lower)
        if upper:
            queryset = queryset.filter(created_at__date__lte=upper)
        distribution = [
            {"status": value, "count": status_filter(queryset, value, today).count()}
            for value in ("active", "expiring", "expired", "scheduled")
        ]
        counts = {item["status"]: item["count"] for item in distribution}
        upcoming = queryset.filter(
            start_date__lte=today, expiration_date__range=(today, today + timedelta(days=30))
        ).order_by("expiration_date", "pk")
        metrics = {
            "total_customers": queryset.count(),
            "active_services": counts["active"] + counts["expiring"],
            "expiring_services": counts["expiring"],
            "expired_services": counts["expired"],
            "scheduled_services": counts["scheduled"],
            "active_administrators": User.objects.filter(
                is_active=True, role__in=[User.Role.SUPER_ADMIN, User.Role.ADMIN]
            ).count(),
            "expiring_7_days": upcoming.filter(expiration_date__lte=today + timedelta(days=7)).count(),
        }
        months = []
        current = today.replace(day=1)
        for _ in range(6):
            months.append(current)
            current = (current - timedelta(days=1)).replace(day=1)
        monthly = (
            queryset.filter(created_at__date__gte=months[-1])
            .annotate(month=TruncMonth("created_at", tzinfo=timezone.get_current_timezone()))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        monthly_counts = {item["month"].date(): item["count"] for item in monthly}
        growth = [
            {"month": month.isoformat(), "count": monthly_counts.get(month, 0)} for month in reversed(months)
        ]
        activities = AuditLog.objects.select_related("actor")
        if request.user.role == User.Role.OPERATOR:
            activities = activities.none()
        if lower:
            activities = activities.filter(created_at__date__gte=lower)
        if upper:
            activities = activities.filter(created_at__date__lte=upper)
        return Response(
            {
                "metrics": metrics,
                "growth": growth,
                "distribution": distribution,
                "upcoming_expirations": CustomerSerializer(upcoming[:6], many=True).data,
                "recent_customers": CustomerSerializer(
                    queryset.order_by("-created_at", "-pk")[:6], many=True
                ).data,
                "recent_activities": AuditSerializer(activities[:8], many=True).data,
            }
        )
