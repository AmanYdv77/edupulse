"""
Development settings for EduPulse.
Enforces that the database name ends with '_dev'.
"""

import os

from .base import *

if not MODEL_ARTIFACT_DIR:
    MODEL_ARTIFACT_DIR = str(BASE_DIR.parent / "artifacts" / "models")

require_db_name(allowed_suffix="_dev")

# Fallback to local memory cache if Redis is not explicitly configured
if "REDIS_URL" not in os.environ and "REDIS_CACHE_URL" not in os.environ:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "edupulse-dev-locmem",
            "TIMEOUT": 300,
        }
    }
