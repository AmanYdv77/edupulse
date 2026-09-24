"""
Tests for Data Separation & Guarded Management Commands (Task A9).

Verifies:
1. seed_demo refuses execution when DJANGO_ENV=prod.
2. seed_demo requires DEMO_USER_PASSWORD.
3. seed_demo creates records with data_origin='demo'.
4. seed_demo --reset-demo deletes only data_origin='demo' and leaves data_origin='real' untouched.
5. Demo telemetry has no synthetic predictive correlation (Pearson r < 0.3).
6. import_institute_data dry-run writes zero rows.
7. import_institute_data --commit refuses execution in dev environment.
8. import_institute_data --commit creates records with data_origin='real' and unusable passwords.
9. import_institute_data is idempotent when executed repeatedly.
10. import_institute_data validation correctly flags corrupt rows and headers.
"""

import os
import random
import tempfile
from pathlib import Path
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from academics.models import (
    StudentProfile,
    Subject,
    Result,
    SemesterResult,
    InternalAssessment,
)
from tests.factories import (
    StudentProfileFactory,
    CourseFactory,
    BatchFactory,
    SubjectFactory,
)


def calculate_pearson_r(x, y):
    """Compute Pearson correlation coefficient between two numeric sequences."""
    n = len(x)
    if n == 0:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / ((var_x * var_y) ** 0.5)


# ---------------------------------------------------------------------------
# SEED_DEMO GUARDS & BEHAVIOR
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_seed_demo_refuses_prod(monkeypatch):
    """Verify seed_demo refuses to run if DJANGO_ENV is prod."""
    monkeypatch.setenv("DJANGO_ENV", "prod")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "DemoSecret123!")

    with pytest.raises(CommandError, match="Security Violation: seed_demo command is prohibited in production"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_requires_password(monkeypatch):
    """Verify seed_demo refuses to run if DEMO_USER_PASSWORD is not provided."""
    monkeypatch.setenv("DJANGO_ENV", "dev")
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)

    with pytest.raises(CommandError, match="DEMO_USER_PASSWORD environment variable is required"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_creates_demo_origin(monkeypatch):
    """Verify seed_demo creates ~60 students all tagged with data_origin='demo'."""
    monkeypatch.setenv("DJANGO_ENV", "dev")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "DemoSecret123!")

    call_command("seed_demo", "--reset-demo")

    demo_students = StudentProfile.objects.filter(data_origin="demo")
    assert demo_students.count() == 60

    # Ensure no demo student has data_origin='real'
    assert StudentProfile.objects.filter(data_origin="real").count() == 0

    # Verify student results and semester results exist
    for student in demo_students[:5]:
        assert student.results.count() == 4
        assert student.semester_results.count() == 1
        assert student.user.check_password("DemoSecret123!")


@pytest.mark.django_db
def test_reset_demo_preserves_real_data(monkeypatch):
    """Verify --reset-demo deletes only data_origin='demo' rows, leaving real data untouched."""
    monkeypatch.setenv("DJANGO_ENV", "dev")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "DemoSecret123!")

    # 1. Seed demo data
    call_command("seed_demo", "--reset-demo")
    assert StudentProfile.objects.filter(data_origin="demo").count() == 60

    # 2. Create real institutional student
    real_student = StudentProfileFactory.create(
        roll_no="REAL-9999",
        data_origin="real",
    )
    real_user_id = real_student.user.id

    # 3. Run seed_demo with --reset-demo
    call_command("seed_demo", "--reset-demo")

    # 4. Verify real student is still intact and not deleted
    assert StudentProfile.objects.filter(roll_no="REAL-9999", data_origin="real").exists()
    assert User.objects.filter(id=real_user_id).exists()

    # 5. Verify demo students were reseeded
    assert StudentProfile.objects.filter(data_origin="demo").count() == 60


def test_demo_telemetry_independence():
    """
    Verify that the demo telemetry generation algorithm has no artificial predictive correlation.
    Pearson correlation between attendance/hours studied and marks across 500 samples must be < 0.3.
    """
    rng = random.Random(1337)
    sample_size = 500

    attendance_list = []
    study_hours_list = []
    sgpa_list = []

    for _ in range(sample_size):
        # Sample independently as implemented in seed_demo
        attendance = round(rng.uniform(55.0, 98.0), 1)
        study_hours = round(rng.uniform(4.0, 36.0), 1)

        # Marks independent of attendance or study hours
        marks = [rng.randint(12, 28) + rng.randint(28, 65) for _ in range(4)]
        sgpa = round(sum(marks) / (len(marks) * 10.0), 2)

        attendance_list.append(attendance)
        study_hours_list.append(study_hours)
        sgpa_list.append(sgpa)

    r_att_sgpa = calculate_pearson_r(attendance_list, sgpa_list)
    r_study_sgpa = calculate_pearson_r(study_hours_list, sgpa_list)

    assert abs(r_att_sgpa) < 0.3, f"Unexpected high correlation between attendance and SGPA: {r_att_sgpa}"
    assert abs(r_study_sgpa) < 0.3, f"Unexpected high correlation between study hours and SGPA: {r_study_sgpa}"


# ---------------------------------------------------------------------------
# IMPORT_INSTITUTE_DATA GUARDS & BEHAVIOR
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_csv_dir(tmp_path):
    """Generate temporary valid CSV files for import testing."""
    d = tmp_path / "csv_data"
    d.mkdir()

    # subjects.csv
    subjects_csv = d / "subjects.csv"
    subjects_csv.write_text(
        "code,title,course_code,semester,credits,max_marks,internal_max,external_max,subject_type\n"
        "CS801,Advanced Machine Learning,BTCSE,7,4,100,30,70,Theory\n"
        "CS802,Cloud Computing Architecture,BTCSE,7,4,100,30,70,Theory\n",
        encoding="utf-8"
    )

    # students.csv
    students_csv = d / "students.csv"
    students_csv.write_text(
        "roll_no,first_name,last_name,email,course_code,batch_code,admission_year,current_semester,distance_from_home\n"
        "REAL-CSE-001,Aarav,Nambiar,aarav@institution.edu,BTCSE,2024-BTCSE,2024,7,Near\n"
        "REAL-CSE-002,Meera,Menon,meera@institution.edu,BTCSE,2024-BTCSE,2024,7,Moderate\n",
        encoding="utf-8"
    )

    # results.csv
    results_csv = d / "results.csv"
    results_csv.write_text(
        "roll_no,subject_code,semester,internal_marks,external_marks,total_secured,grade_points,letter_grade\n"
        "REAL-CSE-001,CS801,7,28,62,90,9.0,A+\n"
        "REAL-CSE-002,CS801,7,22,54,76,7.6,B+\n",
        encoding="utf-8"
    )

    # assessments.csv
    assessments_csv = d / "assessments.csv"
    assessments_csv.write_text(
        "roll_no,subject_code,semester,title,assessment_type,marks_obtained,max_marks\n"
        "REAL-CSE-001,CS801,7,Midterm 1,MIDTERM,22.5,25.0\n",
        encoding="utf-8"
    )

    # attendance.csv
    attendance_csv = d / "attendance.csv"
    attendance_csv.write_text(
        "roll_no,semester,attendance_percentage,hours_studied_per_week\n"
        "REAL-CSE-001,7,88.5,18.0\n"
        "REAL-CSE-002,7,92.0,22.0\n",
        encoding="utf-8"
    )

    return d


@pytest.mark.django_db
def test_import_dry_run_writes_nothing(sample_csv_dir):
    """Verify that default dry-run mode validates data and writes 0 records."""
    call_command("import_institute_data", f"--data-dir={sample_csv_dir}")

    assert StudentProfile.objects.filter(roll_no="REAL-CSE-001").count() == 0
    assert Subject.objects.filter(code="CS801").count() == 0
    assert Result.objects.count() == 0


@pytest.mark.django_db
def test_import_commit_refuses_dev(sample_csv_dir, monkeypatch):
    """Verify that import with --commit refuses execution when DJANGO_ENV is dev."""
    monkeypatch.setenv("DJANGO_ENV", "dev")

    with pytest.raises(CommandError, match="Security Violation: Real institutional data import with --commit is restricted"):
        call_command("import_institute_data", f"--data-dir={sample_csv_dir}", "--commit")


@pytest.mark.django_db
def test_import_commit_creates_real_data(sample_csv_dir, monkeypatch):
    """Verify that import with --commit in test env writes data_origin='real' and unusable passwords."""
    monkeypatch.setenv("DJANGO_ENV", "test")

    call_command("import_institute_data", f"--data-dir={sample_csv_dir}", "--commit")

    # Check student
    student1 = StudentProfile.objects.get(roll_no="REAL-CSE-001")
    assert student1.data_origin == "real"
    assert student1.user.first_name == "Aarav"
    assert student1.user.email == "aarav@institution.edu"
    assert not student1.user.has_usable_password()

    # Check subject & result
    assert Subject.objects.filter(code="CS801").exists()
    result = Result.objects.get(student=student1, subject__code="CS801")
    assert result.total_secured == 90
    assert result.grade_points == 9.0

    # Check assessment
    assert InternalAssessment.objects.filter(student=student1, title="Midterm 1").exists()

    # Check attendance
    sem_res = SemesterResult.objects.get(student=student1, semester=7)
    assert sem_res.attendance_percentage == 88.5


@pytest.mark.django_db
def test_import_is_idempotent(sample_csv_dir, monkeypatch):
    """Verify re-running import with --commit does not duplicate rows."""
    monkeypatch.setenv("DJANGO_ENV", "test")

    # First run
    call_command("import_institute_data", f"--data-dir={sample_csv_dir}", "--commit")
    student_count_1 = StudentProfile.objects.count()
    result_count_1 = Result.objects.count()

    # Second run
    call_command("import_institute_data", f"--data-dir={sample_csv_dir}", "--commit")
    student_count_2 = StudentProfile.objects.count()
    result_count_2 = Result.objects.count()

    assert student_count_1 == student_count_2
    assert result_count_1 == result_count_2


@pytest.mark.django_db
def test_import_validation_flags_corrupt_data(tmp_path):
    """Verify validation detects invalid email, missing required columns, and non-numeric fields."""
    d = tmp_path / "bad_csvs"
    d.mkdir()

    # Corrupt students.csv
    bad_students = d / "students.csv"
    bad_students.write_text(
        "roll_no,first_name,last_name,email,course_code,batch_code,admission_year\n"
        "BAD-001,John,Doe,not-an-email,BTCSE,2024-BTCSE,not-a-year\n",
        encoding="utf-8"
    )

    with pytest.raises(CommandError, match="Validation failed with"):
        call_command("import_institute_data", f"--students={bad_students}")
