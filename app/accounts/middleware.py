"""
Middleware for security and caching controls.
"""


class NoCacheAuthenticatedMiddleware:
    """
    Prevents browsers from caching authenticated HTML pages in the back/forward cache (bfcache).
    This eliminates stale CSRF tokens on back-navigation and prevents unauthorized visual history exposure.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            content_type = response.headers.get("Content-Type", "") if hasattr(response, "headers") else response.get("Content-Type", "")
            if "text/html" in content_type:
                response["Cache-Control"] = "no-store, private"
                response["Pragma"] = "no-cache"
        return response
