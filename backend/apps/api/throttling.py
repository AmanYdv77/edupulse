from rest_framework.throttling import UserRateThrottle, SimpleRateThrottle


class UserReadRateThrottle(UserRateThrottle):
    """
    Limits authenticated user read requests to 120/minute.
    Applies only to SAFE_METHODS (GET, HEAD, OPTIONS).
    """
    scope = "user_read"

    def allow_request(self, request, view):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


class UserWriteRateThrottle(UserRateThrottle):
    """
    Limits authenticated user write requests to 30/minute.
    Applies only to mutating methods (POST, PUT, PATCH, DELETE).
    """
    scope = "user_write"

    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


class LoginRateThrottle(SimpleRateThrottle):
    """
    Throttles login attempts to 5/minute per IP and username.
    """
    scope = "auth"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        username = request.data.get("username", "") if hasattr(request, "data") else ""
        return f"throttle_login_{ident}_{username.strip().lower()}"


class ExportRateThrottle(UserRateThrottle):
    """
    Limits authenticated user data export requests (e.g. at-risk CSV) to 5/hour per user.
    """
    scope = "export"

