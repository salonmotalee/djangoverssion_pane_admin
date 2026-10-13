from django.contrib.auth.backends import ModelBackend

from core.models import User


class OrganizationBackend(ModelBackend):
    def authenticate(self, request, organization_slug=None, portal_username=None, password=None, **kwargs):
        if organization_slug is None or portal_username is None or password is None:
            return None
        user = (
            User.objects.select_related("organization")
            .filter(
                role=User.Role.TENANT,
                organization__slug=organization_slug,
                organization__deleted_at__isnull=True,
                portal_username=portal_username.casefold(),
            )
            .first()
        )
        if user is None:
            User().set_password(password)  # Match password-hashing cost for unknown accounts.
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return bool(
            super().user_can_authenticate(user)
            and user.role == User.Role.TENANT
            and user.organization_id
            and user.organization.deleted_at is None
        )

    def get_user(self, user_id):
        user = User.objects.select_related("organization").filter(pk=user_id).first()
        return user if user is not None and self.user_can_authenticate(user) else None
