"""
Test settings for EduPulse.
Enforces that the database name ends with '_test'.
"""

from .base import *

require_db_name(allowed_suffix="_test")
