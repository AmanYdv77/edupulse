import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run_django_code(code: str, env_vars: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run a Python snippet with a controlled environment from REPO_ROOT."""
    env = os.environ.copy()
    # Clear out any existing DJANGO_* vars to ensure test isolation
    for key in list(env.keys()):
        if key.startswith("DJANGO_"):
            del env[key]

    if env_vars is not None:
        env.update(env_vars)

    cmd = [
        PYTHON,
        "-c",
        (
            "import sys; sys.path.insert(0, 'app'); "
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resultplatform.settings'); "
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
        result = run_django_code(
            "from django.conf import settings; print('SECRET:', settings.SECRET_KEY)",
            env_vars={},
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
            env_vars={"DJANGO_SECRET_KEY": "test-key-for-unit-tests-only"},
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("DEBUG: False", result.stdout)

    def test_allowed_hosts_fallback_when_debug_true(self):
        """When DEBUG is true and DJANGO_ALLOWED_HOSTS is empty, ALLOWED_HOSTS falls back to localhost."""
        result = run_django_code(
            "from django.conf import settings; print('HOSTS:', settings.ALLOWED_HOSTS)",
            env_vars={
                "DJANGO_SECRET_KEY": "test-key-for-unit-tests-only",
                "DJANGO_DEBUG": "True",
            },
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("['localhost', '127.0.0.1']", result.stdout)

    def test_allowed_hosts_parsed_from_env(self):
        """ALLOWED_HOSTS correctly parses comma-separated values from DJANGO_ALLOWED_HOSTS."""
        result = run_django_code(
            "from django.conf import settings; print('HOSTS:', settings.ALLOWED_HOSTS)",
            env_vars={
                "DJANGO_SECRET_KEY": "test-key-for-unit-tests-only",
                "DJANGO_DEBUG": "False",
                "DJANGO_ALLOWED_HOSTS": "edupulse.example.com,api.example.com",
            },
        )
        self.assertEqual(result.returncode, 0, f"Failed with: {result.stderr}")
        self.assertIn("['edupulse.example.com', 'api.example.com']", result.stdout)


if __name__ == "__main__":
    unittest.main()
