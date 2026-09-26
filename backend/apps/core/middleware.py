"""
Security headers and Content-Security-Policy (CSP) middleware for EduPulse.
"""

from typing import Callable
from django.http import HttpRequest, HttpResponse


class SecurityHeadersMiddleware:
    """
    Applies strict Content-Security-Policy, X-Content-Type-Options,
    and Referrer-Policy headers to all outgoing HTTP responses.
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Set CSP header
        response.headers.setdefault("Content-Security-Policy", self.CSP_POLICY)

        # Set MIME-type sniffing protection
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Set Referrer-Policy
        response.headers.setdefault("Referrer-Policy", "same-origin")

        return response
