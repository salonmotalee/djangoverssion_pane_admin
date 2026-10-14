"""Environment driven settings, with a local-only development secret."""

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


def env_list(name, default):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY is required unless DEBUG=true.")
    secret_file = BASE_DIR / ".local-secret"
    try:
        fd = os.open(secret_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secrets.token_urlsafe(64))
    SECRET_KEY = secret_file.read_text(encoding="utf-8").strip()
    if not SECRET_KEY:
        raise ImproperlyConfigured("The local development secret is empty.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:3000/").strip()
try:
    frontend_url = urlsplit(FRONTEND_URL)
    valid_frontend_url = (
        frontend_url.scheme in {"http", "https"}
        and frontend_url.hostname
        and not frontend_url.username
        and not frontend_url.password
        and not frontend_url.query
        and not frontend_url.fragment
    )
    frontend_url.port  # Validate the optional port as well as the hostname.
except ValueError:
    valid_frontend_url = False
if not valid_frontend_url:
    raise ImproperlyConfigured("FRONTEND_URL must be an absolute HTTP(S) URL without credentials or query.")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "portal",
    "operations",
    "support",
    "staff",
    "scheduling",
    "attendance",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "portal.middleware.RealmSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
        conn_max_age=60,
    )
}
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"]["OPTIONS"] = {"timeout": 20, "transaction_mode": "IMMEDIATE"}
AUTH_USER_MODEL = "core.User"
AUTHENTICATION_BACKENDS = [
    "core.authentication.InternalBackend",
    "portal.authentication.OrganizationBackend",
    "staff.authentication.SupervisorBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.IsInternalUser"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SESSION_COOKIE_HTTPONLY = True
PORTAL_SESSION_COOKIE_NAME = "damavand_portal_session"
PORTAL_SESSION_COOKIE_PATH = "/api/organizations/"
SUPERVISOR_SESSION_COOKIE_NAME = "damavand_supervisor_session"
SUPERVISOR_SESSION_COOKIE_PATH = "/api/organizations/"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "28800"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
CSRF_FAILURE_VIEW = "core.views.csrf_failure"
# Trust forwarded HTTPS only when the deployment proxy strips user supplied headers.
if env_bool("TRUST_PROXY_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
