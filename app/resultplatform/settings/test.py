"""
Test settings for EduPulse.
Enforces that the database name ends with '_test'.
"""
import os
import sys
from pathlib import Path

# Default secret key for testing isolation if not provided in environment
os.environ.setdefault("DJANGO_SECRET_KEY", "insecure-test-secret-key-for-pytest-infra-only-32chars")

# Default test database URL pointing to local Docker PostgreSQL instance
DEFAULT_TEST_DB = "postgres://postgres:edupulse_dev_secret_pw@127.0.0.1:55432/edupulse_test"

# If DATABASE_URL is not explicitly provided in environment or .env, default to DEFAULT_TEST_DB
if "DATABASE_URL" not in os.environ:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    env_file = repo_root / ".env"
    db_url_in_env = None
    if env_file.is_file():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    db_url_in_env = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not db_url_in_env:
        os.environ["DATABASE_URL"] = DEFAULT_TEST_DB

from .base import *

# Pre-flight environment guards
if os.environ.get("DJANGO_ENV", "").strip().lower() == "prod":
    sys.stderr.write("Security Violation: Test suite cannot run in production environment (DJANGO_ENV=prod).\n")
    sys.exit(2)

db_name = DATABASES["default"].get("NAME", "")
if not db_name.endswith("_test"):
    sys.stderr.write(
        f"Security Violation: Database name '{db_name}' must end with '_test' for this environment.\n"
    )
    sys.exit(2)

# Ensure Django test runner uses the pre-created test database directly
DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"]["NAME"] = DATABASES["default"]["NAME"]
