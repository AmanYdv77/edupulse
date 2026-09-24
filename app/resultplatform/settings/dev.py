"""
Development settings for EduPulse.
Enforces that the database name ends with '_dev'.
"""

from .base import *

require_db_name(allowed_suffix="_dev")
