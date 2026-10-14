"""Separate central, organization and supervisor cookies using SessionStore.

No global settings are mutated. Each request selects its own session namespace.
The portal response follows Django 5.2 SessionMiddleware's expiry/save semantics.
"""

import re
import time

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


class RealmSessionMiddleware(SessionMiddleware):
    def process_request(self, request):
        request.is_supervisor_request = bool(re.match(r"^/api/organizations/[^/]+/supervisor/", request.path))
        request.is_portal_request = request.path.startswith(settings.PORTAL_SESSION_COOKIE_PATH)
        if not request.is_portal_request:
            super().process_request(request)
            # Preserve existing central sessions after introducing a scoped backend.
            if request.session.get("_auth_user_backend") == "django.contrib.auth.backends.ModelBackend":
                request.session["_auth_user_backend"] = "core.authentication.InternalBackend"
            return
        name = (
            settings.SUPERVISOR_SESSION_COOKIE_NAME
            if request.is_supervisor_request
            else settings.PORTAL_SESSION_COOKIE_NAME
        )
        request.session = self.SessionStore(request.COOKIES.get(name))

    def process_response(self, request, response):
        if not request.is_portal_request:
            return super().process_response(request, response)
        response["Cache-Control"] = "private, no-store"
        session = getattr(request, "session", None)
        if session is None:
            return response
        name, path = (
            (settings.SUPERVISOR_SESSION_COOKIE_NAME, settings.SUPERVISOR_SESSION_COOKIE_PATH)
            if request.is_supervisor_request
            else (settings.PORTAL_SESSION_COOKIE_NAME, settings.PORTAL_SESSION_COOKIE_PATH)
        )
        if name in request.COOKIES and session.is_empty():
            response.delete_cookie(
                name,
                path=path,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ("Cookie",))
        else:
            if session.accessed:
                patch_vary_headers(response, ("Cookie",))
            if (
                (session.modified or settings.SESSION_SAVE_EVERY_REQUEST)
                and not session.is_empty()
                and response.status_code < 500
            ):
                if session.get_expire_at_browser_close():
                    max_age = expires = None
                else:
                    max_age = session.get_expiry_age()
                    expires = http_date(time.time() + max_age)
                try:
                    session.save()
                except UpdateError as exc:
                    raise SessionInterrupted("نشست در درخواست دیگری بسته شده است.") from exc
                response.set_cookie(
                    name,
                    session.session_key,
                    max_age=max_age,
                    expires=expires,
                    path=path,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    secure=settings.SESSION_COOKIE_SECURE or None,
                    httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
                patch_vary_headers(response, ("Cookie",))
        return response
