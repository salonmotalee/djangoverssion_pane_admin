"""Entry point for users opening the API server in their browser."""

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_safe


@require_safe
def frontend_entry(request):
    response = HttpResponseRedirect(settings.FRONTEND_URL)
    response["Cache-Control"] = "no-store"
    return response
