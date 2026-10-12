from django.urls import include, path

from .views import frontend_entry

urlpatterns = [path("", frontend_entry, name="frontend-entry"), path("api/", include("core.urls"))]
