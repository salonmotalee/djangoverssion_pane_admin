"""The public slug is an immutable routing identifier, never a credential."""

import re
import secrets

from django.core.exceptions import ValidationError

RESERVED_SLUGS = frozenset(
    {
        "api",
        "admin",
        "login",
        "logout",
        "dashboard",
        "customers",
        "users",
        "activity",
        "alerts",
        "profile",
        "organizations",
        "static",
        "media",
        "fonts",
        "assets",
        "health",
        "robots",
        "sitemap",
        "favicon",
        "next",
        "_next",
        "auth",
        "settings",
        "account",
        "support",
        "help",
        "register",
        "signup",
        "portal",
    }
)


def generate_slug():
    return "hall-" + secrets.token_hex(6)


def validate_portal_slug(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) or not 3 <= len(value) <= 48:
        raise ValidationError("نشانی باید ۳ تا ۴۸ حرف کوچک انگلیسی، عدد یا خط تیره بین واژه‌ها باشد.")
    if value in RESERVED_SLUGS:
        raise ValidationError("این نشانی برای بخش‌های سامانه رزرو شده است.")
