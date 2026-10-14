from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ValidationError

from .models import SupervisorAccount, normalized_phone


class SupervisorBackend(BaseBackend):
    def authenticate(self, request, organization_slug=None, supervisor_phone=None, password=None, **kwargs):
        if organization_slug is None or supervisor_phone is None or password is None:
            return None
        try:
            phone = normalized_phone(supervisor_phone)
        except ValidationError:
            SupervisorAccount().set_password(password)
            return None
        account = (
            SupervisorAccount.objects.select_related("organization", "supervisor")
            .filter(organization__slug=organization_slug, phone=phone, is_active=True)
            .first()
        )
        if account is None or not account.access_is_valid:
            SupervisorAccount().set_password(password)
            return None
        if account.check_password(password):
            return account
        return None

    def get_user(self, user_id):
        account = (
            SupervisorAccount.objects.select_related("organization", "supervisor").filter(pk=user_id).first()
        )
        return account if account is not None and account.access_is_valid else None
