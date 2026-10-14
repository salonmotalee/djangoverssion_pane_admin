from django.urls import include, path

from .views import (
    OrganizationAppearanceView,
    OrganizationDashboardView,
    OrganizationLoginView,
    OrganizationLogoutView,
    PublicOrganizationView,
)

urlpatterns = [
    path("<slug:slug>/", include("staff.urls")),
    path("<slug:slug>/", include("scheduling.urls")),
    path("<slug:slug>/", include("attendance.urls")),
    path("<slug:slug>/public/", PublicOrganizationView.as_view()),
    path("<slug:slug>/login/", OrganizationLoginView.as_view()),
    path("<slug:slug>/dashboard/", OrganizationDashboardView.as_view()),
    path("<slug:slug>/appearance/", OrganizationAppearanceView.as_view()),
    path("<slug:slug>/logout/", OrganizationLogoutView.as_view()),
    path("<slug:slug>/", include("operations.urls")),
]
