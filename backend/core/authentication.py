from django.contrib.auth.backends import ModelBackend
from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication


class InternalBackend(ModelBackend):
    """Django's normal credentials, restricted to the central identity realm."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and user.organization_id is None and user.role != "tenant"


class SessionAuthentication(DRFSessionAuthentication):
    """Expose expired/absent sessions as 401, while permission failures remain 403."""

    def authenticate_header(self, request):
        return "Session"
