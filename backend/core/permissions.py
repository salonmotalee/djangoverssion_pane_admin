from rest_framework.permissions import BasePermission

from .models import User


class IsAdministrator(BasePermission):
    message = "این بخش فقط برای مدیران قابل دسترسی است."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and request.user.role
            in {
                User.Role.SUPER_ADMIN,
                User.Role.ADMIN,
            }
        )
