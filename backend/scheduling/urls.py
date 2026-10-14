from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ScheduleApplyView,
    ScheduleAuditView,
    ScheduleCopyPreviewView,
    SchedulePreviewView,
    ScheduleView,
    SupervisorScheduleView,
    WorkShiftViewSet,
)

router = DefaultRouter()
router.register("work-shifts", WorkShiftViewSet, basename="organization-work-shift")

urlpatterns = [
    path("schedule/", ScheduleView.as_view()),
    path("schedule/preview/", SchedulePreviewView.as_view()),
    path("schedule/copy-preview/", ScheduleCopyPreviewView.as_view()),
    path("schedule/apply/", ScheduleApplyView.as_view()),
    path("schedule/audit/", ScheduleAuditView.as_view()),
    path("supervisor/schedule/", SupervisorScheduleView.as_view()),
    path("", include(router.urls)),
]
