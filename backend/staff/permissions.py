from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission

from operations.models import Hall

from .models import SupervisorAccount


class IsSupervisor(BasePermission):
    message = "برای ادامه وارد پرتال مراقب شوید."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and isinstance(request.user, SupervisorAccount)
            and request.user.access_is_valid
        )


def current_supervisor(request, slug):
    if not request.user.is_authenticated:
        raise NotAuthenticated("برای ادامه وارد پرتال مراقب شوید.")
    if not isinstance(request.user, SupervisorAccount):
        raise PermissionDenied("این نشست متعلق به مراقب نیست.")
    # Reload for live revocation and to avoid trusting a stale injected principal.
    account = (
        SupervisorAccount.objects.select_related("organization", "supervisor")
        .filter(pk=request.user.pk)
        .first()
    )
    if account is None or account.organization.slug != slug or not account.access_is_valid:
        raise PermissionDenied("اجازهٔ دسترسی به این مجموعه را ندارید.")
    if account.get_session_auth_hash() != request.user.get_session_auth_hash():
        raise PermissionDenied("حساب ورود تغییر کرده است؛ دوباره وارد شوید.")
    return account


def authorized_halls(account):
    # Planning shifts intentionally have no bearing on authorization.
    return Hall.objects.filter(
        organization_id=account.organization_id,
        is_active=True,
        supervisor_assignments__supervisor_id=account.supervisor_id,
    ).order_by("name", "pk")
