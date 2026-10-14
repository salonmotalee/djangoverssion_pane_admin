from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Customer
from core.services import failed_login, login_is_limited, successful_login, throttle_keys, throttle_records
from operations.models import Supervisor
from portal.views import IsOrganizationUser, owned_organization, public_organization

from .models import SupervisorAccount, normalized_phone
from .permissions import IsSupervisor, current_supervisor
from .serializers import PasswordChangeSerializer, ProvisionSerializer, SupervisorCredentials, account_payload
from .services import access_payload, check_password, provision_supervisor


@method_decorator(csrf_protect, name="dispatch")
class SupervisorLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, slug):
        credentials = SupervisorCredentials(data=request.data)
        credentials.is_valid(raise_exception=True)
        organization = public_organization(slug)
        from django.core.exceptions import ValidationError

        try:
            username = normalized_phone(credentials.validated_data["username"])
        except ValidationError:
            username = credentials.validated_data["username"]
        keys = throttle_keys(request, f"supervisor:{organization.pk}:{username}")
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
                supervisor_phone=username,
                password=credentials.validated_data["password"],
            )
            account = None
            if authenticated is not None and locked.deleted_at is None:
                account = (
                    SupervisorAccount.objects.select_for_update()
                    .select_related("organization", "supervisor")
                    .filter(
                        pk=authenticated.pk,
                        organization=locked,
                        is_active=True,
                        password=authenticated.password,
                        session_version=authenticated.session_version,
                    )
                    .first()
                )
            if account is None or not account.access_is_valid:
                failed_login(counters)
                return Response({"detail": "شمارهٔ همراه یا رمز عبور صحیح نیست."}, status=400)
            successful_login(counters, keys[0][0])
            login(request, account, backend="staff.authentication.SupervisorBackend")
        return Response(account_payload(account))


class SupervisorMeView(APIView):
    permission_classes = [IsSupervisor]

    def get(self, request, slug):
        return Response(account_payload(current_supervisor(request, slug)))


class SupervisorProfileView(SupervisorMeView):
    def patch(self, request, slug):
        original = current_supervisor(request, slug)
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            Customer.objects.select_for_update().get(pk=original.organization_id)
            account = current_supervisor(request, slug)
            from rest_framework.exceptions import ValidationError

            if not account.check_password(serializer.validated_data["current_password"]):
                raise ValidationError({"current_password": "رمز عبور فعلی صحیح نیست."})
            check_password(serializer.validated_data["new_password"], account)
            account.set_password(serializer.validated_data["new_password"])
            account.save(update_fields=["password"])
            update_session_auth_hash(request, account)
        return Response(account_payload(account))


class SupervisorLogoutView(APIView):
    permission_classes = [IsSupervisor]

    def post(self, request, slug):
        current_supervisor(request, slug)
        logout(request)
        return Response(status=204)


class SupervisorAccessView(APIView):
    permission_classes = [IsOrganizationUser]

    def get(self, request, slug, supervisor_id):
        organization = owned_organization(request, slug)
        supervisor = get_object_or_404(Supervisor, pk=supervisor_id, organization=organization)
        account = (
            SupervisorAccount.objects.select_related("organization", "supervisor")
            .filter(supervisor=supervisor)
            .first()
        )
        return Response(access_payload(supervisor, account))

    def put(self, request, slug, supervisor_id):
        organization = owned_organization(request, slug)
        serializer = ProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            provision_supervisor(organization, supervisor_id, request.user, **serializer.validated_data)
        )
