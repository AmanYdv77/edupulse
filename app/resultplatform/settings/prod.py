"""
Production settings for EduPulse.
Enforces that DEBUG is False and database name does NOT end with '_dev', '_test', or '_e2e'.
"""

from django.core.exceptions import ImproperlyConfigured
from .base import *

if DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be False in production.")

require_db_name(disallowed_suffixes=("_dev", "_test", "_e2e"))

# Deployment & HTTPS Security Hardening
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

