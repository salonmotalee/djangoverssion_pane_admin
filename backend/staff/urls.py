from django.urls import path

from .views import (
    SupervisorAccessView,
    SupervisorLoginView,
    SupervisorLogoutView,
    SupervisorMeView,
    SupervisorProfileView,
)

urlpatterns = [
    path("supervisor/login/", SupervisorLoginView.as_view()),
    path("supervisor/logout/", SupervisorLogoutView.as_view()),
    path("supervisor/me/", SupervisorMeView.as_view()),
    path("supervisor/profile/", SupervisorProfileView.as_view()),
    path("supervisor-access/<int:supervisor_id>/", SupervisorAccessView.as_view()),
]
