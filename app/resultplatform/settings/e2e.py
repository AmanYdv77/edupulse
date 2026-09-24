"""
E2E browser test settings for EduPulse.
Enforces that the database name ends with '_e2e'.
"""

from .base import *

if not MODEL_ARTIFACT_DIR:
    MODEL_ARTIFACT_DIR = str(BASE_DIR.parent / "artifacts" / "models")

require_db_name(allowed_suffix="_e2e")

