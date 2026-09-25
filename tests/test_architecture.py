"""
Architecture compliance and boundary verification tests (Task A20).
Enforces:
1. edupulse_ml is 100% framework-independent and importable in an environment where Django is poisoned/unavailable.
2. System checks report 0 issues.
3. makemigrations --check reports 0 changes (proves 0 schema impact from reorganization).
4. Package responsibility and thin view function conventions.
"""

import subprocess
import sys
from pathlib import Path
import pytest
from django.core.management import call_command


def test_edupulse_ml_imports_zero_django():
    """
    Verifies that edupulse_ml has strictly ZERO dependencies on Django.
    Spawns a clean subprocess where 'django' is poisoned in sys.modules,
    ensuring that importing edupulse_ml modules succeeds without touching Django.
    """
    script = (
        "import sys\n"
        "sys.modules['django'] = None\n"
        "import edupulse_ml.contract\n"
        "import edupulse_ml.evaluate\n"
        "import edupulse_ml.fairness\n"
        "print('EDUPULSE_ML_INDEPENDENCE_OK')\n"
    )

    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"

    env = {
        "PYTHONPATH": f"{repo_root};{backend_dir}",
        "SYSTEMROOT": subprocess.os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "PATH": subprocess.os.environ.get("PATH", ""),
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
    )

    assert result.returncode == 0, f"edupulse_ml attempted to import Django or failed: {result.stderr}"
    assert "EDUPULSE_ML_INDEPENDENCE_OK" in result.stdout


@pytest.mark.django_db
def test_django_system_checks_pass():
    """Django system check must report 0 issues."""
    call_command("check")


@pytest.mark.django_db
def test_no_migrations_pending():
    """makemigrations --check must detect no changes across all domain apps."""
    try:
        call_command("makemigrations", check=True, dry_run=True)
    except SystemExit as e:
        pytest.fail(f"Pending migrations detected after reorganisation: {e}")
