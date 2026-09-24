"""
E2E browser test settings for EduPulse.
Enforces that the database name ends with '_e2e'.
"""

from .base import *

require_db_name(allowed_suffix="_e2e")
