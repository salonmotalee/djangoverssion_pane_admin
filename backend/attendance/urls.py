from django.urls import path

from .views import (
    AutomaticFinalizeView,
    AutomaticPreviewView,
    ManagerAttendanceView,
    ManagerCorrectionView,
    ManualAttendanceView,
    PresenceView,
    SupervisorAttendanceView,
    SupervisorDashboardView,
    SupervisorHallsView,
    SupervisorStudentsView,
)

urlpatterns = [
    path("supervisor/dashboard/", SupervisorDashboardView.as_view()),
    path("supervisor/halls/", SupervisorHallsView.as_view()),
    path("supervisor/students/", SupervisorStudentsView.as_view()),
    path("supervisor/presence/", PresenceView.as_view()),
    path("supervisor/attendance/", SupervisorAttendanceView.as_view()),
    path("supervisor/attendance/bulk/", ManualAttendanceView.as_view()),
    path("supervisor/attendance/preview/", AutomaticPreviewView.as_view()),
    path("supervisor/attendance/automatic/", AutomaticFinalizeView.as_view()),
    path("attendance/", ManagerAttendanceView.as_view()),
    path("attendance/corrections/", ManagerCorrectionView.as_view()),
]
