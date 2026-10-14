from django.urls import include, path

from .views import (
    OrganizationDashboardView,
    OrganizationLoginView,
    OrganizationLogoutView,
    PublicOrganizationView,
)

urlpatterns = [
    path("<slug:slug>/public/", PublicOrganizationView.as_view()),
    path("<slug:slug>/login/", OrganizationLoginView.as_view()),
    path("<slug:slug>/dashboard/", OrganizationDashboardView.as_view()),
    path("<slug:slug>/logout/", OrganizationLogoutView.as_view()),
    path("<slug:slug>/", include("operations.urls")),
]
