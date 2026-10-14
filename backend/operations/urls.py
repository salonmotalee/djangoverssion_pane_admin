from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssignmentsView, HallViewSet, StudentViewSet, StudySessionViewSet, SupervisorViewSet

router = DefaultRouter()
router.register("halls", HallViewSet, basename="organization-hall")
router.register("study-sessions", StudySessionViewSet, basename="organization-study-session")
router.register("students", StudentViewSet, basename="organization-student")
router.register("supervisors", SupervisorViewSet, basename="organization-supervisor")

urlpatterns = [path("assignments/", AssignmentsView.as_view()), path("", include(router.urls))]
