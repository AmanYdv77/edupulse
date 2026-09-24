"""
Pytest configuration, database guards, and global fixtures for EduPulse.
"""
import os
import random
from urllib.parse import urlparse
import pytest
from faker import Faker

DEFAULT_TEST_DB = "postgres://postgres:edupulse_dev_secret_pw@127.0.0.1:55432/edupulse_test"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """
    Double-layer pre-flight database guard executed before Django initializes or tests run.
    Enforces that:
    1. DJANGO_ENV is not 'prod'
    2. DATABASE_URL points to a database name ending with '_test'
    Immediately exits with returncode=2 on violation.
    """
    # Guard Layer 1: Strictly disallow prod environment
    django_env = os.environ.get("DJANGO_ENV", "").strip().lower()
    if django_env == "prod":
        pytest.exit(
            "Security Violation: Test suite cannot run in production environment (DJANGO_ENV=prod).",
            returncode=2,
        )

    # Ensure a fallback test secret key is present if not provided in environment
    os.environ.setdefault("DJANGO_SECRET_KEY", "insecure-test-secret-key-for-pytest-infra-only-32chars")

    # Guard Layer 2: Pre-Django DATABASE_URL verification
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Check if DATABASE_URL is defined in root .env file
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if db_url:
        parsed = urlparse(db_url)
        db_name = parsed.path.lstrip("/").split("?")[0]
        if not db_name.endswith("_test"):
            pytest.exit(
                f"Security Violation: Test suite can only run against a database ending in '_test'. Configured database is '{db_name}'.",
                returncode=2,
            )
        # Ensure os.environ reflects the verified test DATABASE_URL
        os.environ["DATABASE_URL"] = db_url
    else:
        # Default to local Docker test database ending with _test
        os.environ["DATABASE_URL"] = DEFAULT_TEST_DB


@pytest.fixture(scope="session", autouse=True)
def seed_test_randomness():
    """Seed random and Faker generators for reproducible test outcomes."""
    random.seed(42)
    Faker.seed(42)
