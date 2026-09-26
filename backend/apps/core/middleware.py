import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .logging import set_request_id

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIDMiddleware:
    """
    Middleware that ensures every request has a validated correlation ID.
    Reads incoming X-Request-ID, validates format, or generates a UUID4.
    Sets contextvar for logging and returns X-Request-ID in response header.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming_id = request.headers.get("X-Request-ID", "").strip()
        if incoming_id and REQUEST_ID_REGEX.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        set_request_id(request_id)
        request.request_id = request_id

        try:
            response = self.get_response(request)
        finally:
            set_request_id("")

        response.headers["X-Request-ID"] = request_id
        return response


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
