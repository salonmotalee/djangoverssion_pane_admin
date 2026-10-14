from rest_framework.permissions import BasePermission

from core.models import User


def support_staff():
    from django.db.models import Q

    return User.objects.filter(is_active=True, organization__isnull=True).filter(
        Q(role=User.Role.SUPER_ADMIN) | Q(role__in=[User.Role.ADMIN, User.Role.OPERATOR], can_support=True)
    )


class CanUseSupport(BasePermission):
    message = "اجازه دسترسی به پشتیبانی را ندارید."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Never trust a cached permission grant after it has been revoked.
        current = (
            User.objects.select_related("organization").filter(pk=request.user.pk, is_active=True).first()
        )
        if current is None:
            return False
        request.user = current
        slug = view.kwargs.get("slug")
        if slug is not None:
            return bool(
                current.role == User.Role.TENANT
                and current.is_portal_owner
                and current.organization_id
                and current.organization.slug == slug
                and current.organization.deleted_at is None
            )
        return support_staff().filter(pk=current.pk).exists()
