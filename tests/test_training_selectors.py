import subprocess
import pytest
from django.db.models import QuerySet
from academics.models import Result, StudentProfile
from tests.factories import make_university


@pytest.mark.django_db
class TestTrainingSelectors:
    """Verifies that ML training data selectors strictly exclude demo or synthetic data."""

    def test_scripts_directory_contains_no_training_or_seeding_scripts(self):
        """git ls-files scripts must be completely empty; legacy circular training scripts removed."""
        res = subprocess.run(
            ["git", "ls-files", "scripts"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0
        tracked_scripts = res.stdout.strip().splitlines()
        assert not tracked_scripts, f"Found unexpected tracked files in scripts: {tracked_scripts}"

    def test_training_rows_returns_only_real_data(self):
        """training_rows() must only select records from students with data_origin='real'."""
        from predictions.selectors import training_rows

        uni = make_university(students_per_batch=2)
        students = uni["students"]

        # Explicitly designate one student as demo and one as real
        students[0].data_origin = "demo"
        students[0].save(update_fields=["data_origin"])
        students[1].data_origin = "real"
        students[1].save(update_fields=["data_origin"])

        # Fetch training rows
        qs = training_rows()

        # Must return results for the real student only
        assert qs.exists()
        for result in qs:
            assert result.student.data_origin == "real"
            assert result.student_id == students[1].id

    def test_training_rows_refuses_demo_data_flag(self):
        """training_rows() must immediately raise RuntimeError if allow_demo=True is attempted."""
        from predictions.selectors import training_rows

        with pytest.raises(RuntimeError, match="Training data selector strictly prohibits demo data"):
            training_rows(allow_demo=True)

    def test_assert_real_training_data_guard(self):
        """assert_real_training_data() must raise RuntimeError if any demo row is detected."""
        from predictions.selectors import assert_real_training_data

        uni = make_university(students_per_batch=2)
        students = uni["students"]

        # Contaminate with one demo student
        students[0].data_origin = "demo"
        students[0].save(update_fields=["data_origin"])

        demo_results = Result.objects.filter(student__in=students)
        with pytest.raises(RuntimeError, match="Contaminated training data"):
            assert_real_training_data(demo_results)

        # Set all to 'real'
        StudentProfile.objects.filter(id__in=[s.id for s in students]).update(data_origin="real")
        real_results = Result.objects.filter(student__in=students)

        # Should pass without raising
        assert assert_real_training_data(real_results) is True
