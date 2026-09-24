"""
Production settings for EduPulse.
Enforces that DEBUG is False and database name does NOT end with '_dev', '_test', or '_e2e'.
"""

from django.core.exceptions import ImproperlyConfigured
from .base import *

if DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be False in production.")

require_db_name(disallowed_suffixes=("_dev", "_test", "_e2e"))
