import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

DEFAULT_DEV_DB = "postgres://postgres:edupulse_dev_secret_pw@localhost:55432/edupulse_dev"
DEFAULT_TEST_DB = "postgres://postgres:edupulse_dev_secret_pw@localhost:55432/edupulse_test"
DEFAULT_E2E_DB = "postgres://postgres:edupulse_dev_secret_pw@localhost:55432/edupulse_e2e"
DEFAULT_PROD_DB = "postgres://postgres:edupulse_dev_secret_pw@localhost:55432/edupulse_production"


def run_django_code(
    code: str,
    settings_module: str = "config.settings.dev",
    env_vars: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a Python snippet with a controlled environment from REPO_ROOT."""
    env = os.environ.copy()
    # Clear out any existing DJANGO_* vars to ensure test isolation
    for key in list(env.keys()):
        if key.startswith("DJANGO_") or key == "DATABASE_URL":
            del env[key]

    base_env = {
        "DJANGO_SETTINGS_MODULE": settings_module,
        "DJANGO_SECRET_KEY": "test-key-for-unit-tests-only",
        "DATABASE_URL": DEFAULT_DEV_DB,
    }
    if env_vars is not None:
        base_env.update(env_vars)

    env.update(base_env)

    cmd = [
        PYTHON,
        "-c",
        (
            "import sys; sys.path.insert(0, 'backend'); "
            + code
        ),
    ]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


class TestSettingsEnvironment(unittest.TestCase):
    def test_missing_secret_key_raises_error(self):
        """A missing DJANGO_SECRET_KEY must cause settings to raise ImproperlyConfigured and exit non-zero."""
        # Specifically unset DJANGO_SECRET_KEY
        env = os.environ.copy()
        for key in list(env.keys()):
            if key.startswith("DJANGO_") or key == "DATABASE_URL":
                del env[key]
        env["DATABASE_URL"] = DEFAULT_DEV_DB

        cmd = [
            PYTHON,
            "-c",
            "import sys; sys.path.insert(0, 'backend'); from django.conf import settings; print('SECRET:', settings.SECRET_KEY)",
        ]
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0, f"Expected non-zero exit code, got 0. stdout: {result.stdout}")
        self.assertTrue(
            "ImproperlyConfigured" in result.stderr or "DJANGO_SECRET_KEY" in result.stderr,
            f"Expected ImproperlyConfigured in stderr, got: {result.stderr}",
        )

    def test_debug_defaults_to_false(self):
        """DEBUG must default to False when DJANGO_DEBUG is unset."""
        result = run_django_code(
            "from django.conf import settings; print('DEBUG:', settings.DEBUG)",
            env_vars={"DJANGO_DEBUG": ""},
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("DEBUG: False", result.stdout)

    def test_allowed_hosts_fallback_when_debug_true(self):
        """When DEBUG is true and DJANGO_ALLOWED_HOSTS is empty, ALLOWED_HOSTS falls back to localhost."""
        result = run_django_code(
            "from django.conf import settings; print('HOSTS:', settings.ALLOWED_HOSTS)",
            env_vars={
                "DJANGO_DEBUG": "True",
                "DJANGO_ALLOWED_HOSTS": "",
            },
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("['localhost', '127.0.0.1']", result.stdout)

    def test_allowed_hosts_parsed_from_env(self):
        """ALLOWED_HOSTS correctly parses comma-separated values from DJANGO_ALLOWED_HOSTS."""
        result = run_django_code(
            "from django.conf import settings; print('HOSTS:', settings.ALLOWED_HOSTS)",
            env_vars={
                "DJANGO_DEBUG": "False",
                "DJANGO_ALLOWED_HOSTS": "edupulse.example.com,api.example.com",
            },
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("['edupulse.example.com', 'api.example.com']", result.stdout)

    def test_dev_settings_rejects_non_dev_database(self):
        """dev.py must refuse to start if DATABASE_URL does not end with _dev."""
        result = run_django_code(
            "from django.conf import settings; print('DB:', settings.DATABASES['default']['NAME'])",
            settings_module="config.settings.dev",
            env_vars={"DATABASE_URL": DEFAULT_TEST_DB},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must end with '_dev'", result.stderr)

    def test_test_settings_rejects_dev_database(self):
        """test.py must refuse to start if DATABASE_URL does not end with _test."""
        result = run_django_code(
            "from django.conf import settings; print('DB:', settings.DATABASES['default']['NAME'])",
            settings_module="config.settings.test",
            env_vars={"DATABASE_URL": DEFAULT_DEV_DB},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must end with '_test'", result.stderr)

    def test_test_settings_accepts_test_database(self):
        """test.py succeeds when pointed at an _test database."""
        result = run_django_code(
            "from django.conf import settings; print('DB:', settings.DATABASES['default']['NAME'])",
            settings_module="config.settings.test",
            env_vars={"DATABASE_URL": DEFAULT_TEST_DB},
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("DB: edupulse_test", result.stdout)

    def test_prod_settings_rejects_dev_or_test_database(self):
        """prod.py must refuse if database ends in _dev, _test, or _e2e."""
        for disallowed_db in (DEFAULT_DEV_DB, DEFAULT_TEST_DB, DEFAULT_E2E_DB):
            result = run_django_code(
                "from django.conf import settings; print('DB:', settings.DATABASES['default']['NAME'])",
                settings_module="config.settings.prod",
                env_vars={
                    "DJANGO_DEBUG": "False",
                    "DATABASE_URL": disallowed_db,
                },
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not end with", result.stderr)

    def test_prod_settings_rejects_debug_true(self):
        """prod.py must refuse to start if DJANGO_DEBUG is True."""
        result = run_django_code(
            "from django.conf import settings; print('DB:', settings.DATABASES['default']['NAME'])",
            settings_module="config.settings.prod",
            env_vars={
                "DJANGO_DEBUG": "True",
                "DATABASE_URL": DEFAULT_PROD_DB,
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEBUG must be False in production", result.stderr)


if __name__ == "__main__":
    unittest.main()
