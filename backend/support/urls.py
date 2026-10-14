from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import NotificationsView, ReadNotificationsView, StaffView, TicketViewSet

router = SimpleRouter()
router.register("tickets", TicketViewSet, basename="support-ticket")

urlpatterns = [
    path("staff/", StaffView.as_view()),
    path("notifications/", NotificationsView.as_view()),
    path("notifications/read/", ReadNotificationsView.as_view()),
    *router.urls,
]
