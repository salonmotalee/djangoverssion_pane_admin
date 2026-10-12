from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication


class SessionAuthentication(DRFSessionAuthentication):
    """Expose expired/absent sessions as 401, while permission failures remain 403."""

    def authenticate_header(self, request):
        return "Session"
