from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Customer, User
from core.services import (
    failed_login,
    login_is_limited,
    record_audit,
    successful_login,
    throttle_keys,
    throttle_records,
)

from .serializers import PortalProfileSerializer


class IsOrganizationUser(BasePermission):
    message = "این نشست متعلق به پرتال مجموعه نیست."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.role == User.Role.TENANT
            and request.user.is_active
            and request.user.organization_id
            and request.user.organization.deleted_at is None
        )


def public_organization(slug):
    organization = get_object_or_404(Customer, slug=slug, deleted_at__isnull=True)
    if not organization.portal_owner or organization.capacity is None:
        from rest_framework.exceptions import NotFound

        raise NotFound("پرتال این مجموعه در دسترس نیست.")
    return organization


def owned_organization(request, slug):
    if not request.user.is_authenticated:
        raise NotAuthenticated("برای ادامه وارد پرتال شوید.")
    if request.user.role != User.Role.TENANT or not request.user.organization_id:
        raise PermissionDenied("این نشست اجازه ورود به پرتال مجموعه را ندارد.")
    organization = request.user.organization
    if organization.slug != slug or organization.deleted_at is not None or not request.user.is_active:
        raise PermissionDenied("اجازه دسترسی به این مجموعه را ندارید.")
    return organization


class PublicOrganizationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        organization = public_organization(slug)
        return Response({"name": organization.name, "slug": organization.slug})


class LoginCredentials(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


@method_decorator(csrf_protect, name="dispatch")
class OrganizationLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, slug):
        credentials = LoginCredentials(data=request.data)
        credentials.is_valid(raise_exception=True)
        organization = public_organization(slug)
        keys = throttle_keys(request, f"portal:{organization.pk}:{credentials.validated_data['username']}")
        with transaction.atomic():
            counters = throttle_records(keys)
            if login_is_limited(counters):
                return Response(
                    {"detail": "تلاش‌های ورود زیاد است؛ ۱۵ دقیقه بعد دوباره تلاش کنید."},
                    status=429,
                    headers={"Retry-After": "900"},
                )
            locked = Customer.objects.select_for_update().get(pk=organization.pk)
            authenticated = authenticate(
                request,
                organization_slug=slug,
                portal_username=credentials.validated_data["username"],
                password=credentials.validated_data["password"],
            )
            user = None
            if authenticated is not None and locked.deleted_at is None:
                user = (
                    User.objects.select_for_update()
                    .filter(
                        pk=authenticated.pk,
                        role=User.Role.TENANT,
                        organization=locked,
                        is_active=True,
                        password=authenticated.password,
                        portal_session_version=authenticated.portal_session_version,
                    )
                    .first()
                )
            if user is None:
                failed_login(counters)
                return Response({"detail": "نام کاربری یا رمز عبور صحیح نیست."}, status=400)
            successful_login(counters, keys[0][0])
            login(request, user, backend="portal.authentication.OrganizationBackend")
            record_audit(user, "portal_login", locked, f"ورود به پرتال {locked.name}")
        return Response(
            {"username": user.portal_username, "organization": PortalProfileSerializer(locked).data}
        )


class OrganizationDashboardView(APIView):
    permission_classes = [IsOrganizationUser]

    def get(self, request, slug):
        organization = owned_organization(request, slug)
        return Response(
            {
                "username": request.user.portal_username,
                "organization": PortalProfileSerializer(organization).data,
            }
        )


class OrganizationLogoutView(APIView):
    permission_classes = [IsOrganizationUser]

    def post(self, request, slug):
        organization = owned_organization(request, slug)
        record_audit(request.user, "portal_logout", organization, f"خروج از پرتال {organization.name}")
        logout(request)
        return Response(status=204)
