from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditViewSet,
    CsrfView,
    CustomerViewSet,
    DashboardView,
    LoginView,
    LogoutView,
    MeView,
    PasswordView,
    UserViewSet,
)

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("users", UserViewSet, basename="user")
router.register("audit", AuditViewSet, basename="audit")

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("auth/password/", PasswordView.as_view()),
    path("dashboard/", DashboardView.as_view()),
    path("", include(router.urls)),
]
