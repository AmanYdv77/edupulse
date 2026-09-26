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
DEFAULT_TEST_DB = "postgres://postgres:edupulse_dev_secret_pw@127.0.0.1:54432/edupulse_test"

# If DATABASE_URL is not explicitly provided in environment or .env, default to DEFAULT_TEST_DB
if "DATABASE_URL" not in os.environ:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    env_file = repo_root / ".env"
    db_url_in_env = None
    if env_file.is_file():
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # First look for TEST_DATABASE_URL
            for line in lines:
                line = line.strip()
                if line.startswith("TEST_DATABASE_URL="):
                    db_url_in_env = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            # If not found, look for DATABASE_URL ending in _test
            if not db_url_in_env:
                for line in lines:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val.endswith("_test"):
                            db_url_in_env = val
                            break
    if not db_url_in_env:
        os.environ["DATABASE_URL"] = DEFAULT_TEST_DB
    else:
        os.environ["DATABASE_URL"] = db_url_in_env

from .base import *

if not MODEL_ARTIFACT_DIR:
    MODEL_ARTIFACT_DIR = str(BASE_DIR.parent / "artifacts" / "models")

# Ensure test clients (testserver) and local test hosts are allowed
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS + ["localhost", "127.0.0.1", "testserver"]))


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

# Hermetic in-memory cache for test suite
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "edupulse-test-locmem",
        "TIMEOUT": 300,
    }
}

