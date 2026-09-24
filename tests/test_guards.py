"""
Tests verifying double-layer database guards, model factories, and university hierarchy generation.
"""
import os
import subprocess
import sys
from pathlib import Path
import pytest
from django.contrib.auth import get_user_model
from academics.models import (
    University,
    School,
    Department,
    Course,
    Batch,
    Subject,
    TeacherProfile,
    StudentProfile,
    TeachingAssignment,
    Result,
    SemesterResult,
    HabitCheckInLog,
)
from tests.factories import (
    UserFactory,
    StudentUserFactory,
    TeacherUserFactory,
    HODUserFactory,
    DeanUserFactory,
    VCUserFactory,
    RegistrarUserFactory,
    ControllerUserFactory,
    AdminUserFactory,
    UniversityFactory,
    SchoolFactory,
    DepartmentFactory,
    CourseFactory,
    BatchFactory,
    SubjectFactory,
    TeacherProfileFactory,
    StudentProfileFactory,
    TeachingAssignmentFactory,
    ResultFactory,
    SemesterResultFactory,
    HabitCheckInLogFactory,
    make_university,
)

User = get_user_model()
REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_DB_URL = "postgres://postgres:edupulse_dev_secret_pw@127.0.0.1:55432/edupulse_dev"
TEST_DB_URL = "postgres://postgres:edupulse_dev_secret_pw@127.0.0.1:55432/edupulse_test"


# ---------------------------------------------------------------------------
# GUARD TESTS (Subprocess execution testing pytest_configure hook)
# ---------------------------------------------------------------------------

def test_pytest_guard_refuses_dev_database():
    """
    Subprocess test: running pytest with DATABASE_URL pointing to a non-_test database
    (e.g., edupulse_dev) MUST immediately exit with returncode 2 and security violation message.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = DEV_DB_URL
    env["DJANGO_ENV"] = "dev"
    env["DJANGO_SECRET_KEY"] = "test-secret-key-for-guard-checks"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-k",
        "nonexistent_test_filter_for_preflight_check",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, f"Expected returncode 2, got {proc.returncode}. Output:\n{proc.stdout}\n{proc.stderr}"
    output = proc.stdout + proc.stderr
    assert "Security Violation" in output
    assert "edupulse_dev" in output


def test_pytest_guard_refuses_prod_environment():
    """
    Subprocess test: running pytest with DJANGO_ENV=prod MUST immediately exit
    with returncode 2 and security violation message.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DB_URL
    env["DJANGO_ENV"] = "prod"
    env["DJANGO_SECRET_KEY"] = "test-secret-key-for-guard-checks"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-k",
        "nonexistent_test_filter_for_preflight_check",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, f"Expected returncode 2, got {proc.returncode}. Output:\n{proc.stdout}\n{proc.stderr}"
    output = proc.stdout + proc.stderr
    assert "Security Violation" in output
    assert "production environment" in output


# ---------------------------------------------------------------------------
# FACTORY PERSISTENCE & INTEGRITY TESTS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_factories_persist_valid_users():
    """Verify that UserFactory and all 8 role factories persist valid users with unusable passwords and test emails."""
    user_factories = [
        (UserFactory, User.Role.STUDENT),
        (StudentUserFactory, User.Role.STUDENT),
        (TeacherUserFactory, User.Role.TEACHER),
        (HODUserFactory, User.Role.HOD),
        (DeanUserFactory, User.Role.DEAN),
        (VCUserFactory, User.Role.VC),
        (RegistrarUserFactory, User.Role.REGISTRAR),
        (ControllerUserFactory, User.Role.CONTROLLER),
        (AdminUserFactory, User.Role.SYSADMIN),
    ]

    for factory_cls, expected_role in user_factories:
        user = factory_cls.create()
        assert user.pk is not None
        assert user.role == expected_role
        assert user.email.endswith("@example.test")
        assert not user.has_usable_password(), f"{factory_cls.__name__} should have an unusable password"


@pytest.mark.django_db
def test_academic_factories_persist_valid_models():
    """Verify that every academic model factory creates and persists a valid database record."""
    univ = UniversityFactory.create()
    assert univ.pk is not None

    school = SchoolFactory.create()
    assert school.pk is not None
    assert school.university is not None

    dept = DepartmentFactory.create()
    assert dept.pk is not None
    assert dept.school is not None

    course = CourseFactory.create()
    assert course.pk is not None
    assert course.department is not None

    batch = BatchFactory.create()
    assert batch.pk is not None
    assert batch.course is not None

    subject = SubjectFactory.create()
    assert subject.pk is not None
    assert subject.course is not None

    teacher = TeacherProfileFactory.create()
    assert teacher.pk is not None
    assert teacher.user.role == User.Role.TEACHER

    student = StudentProfileFactory.create()
    assert student.pk is not None
    assert student.user.role == User.Role.STUDENT
    assert student.batch is not None

    assign = TeachingAssignmentFactory.create()
    assert assign.pk is not None

    result = ResultFactory.create()
    assert result.pk is not None

    sem_result = SemesterResultFactory.create()
    assert sem_result.pk is not None

    habit = HabitCheckInLogFactory.create()
    assert habit.pk is not None


@pytest.mark.django_db
def test_make_university_creates_connected_hierarchy():
    """Verify that make_university() generates a fully connected academic institution structure."""
    count = 6
    tree = make_university(students_per_batch=count)

    assert tree["university"].pk is not None
    assert tree["school"].university == tree["university"]
    assert tree["department"].school == tree["school"]
    assert tree["course"].department == tree["department"]
    assert tree["batch"].course == tree["course"]

    # Check executives
    for role_key in ("vc", "registrar", "controller", "admin"):
        assert tree["executives"][role_key].pk is not None
        assert tree["executives"][role_key].email.endswith("@example.test")

    # Check teachers and subjects
    assert len(tree["teachers"]) == 2
    assert len(tree["subjects"]) == 2
    assert len(tree["assignments"]) == 2

    # Check students and their relations
    assert len(tree["students"]) == count
    for student in tree["students"]:
        assert student.batch == tree["batch"]
        assert student.course == tree["course"]
        assert student.department == tree["department"]
        assert student.school == tree["school"]
        assert student.user.email.endswith("@example.test")
        assert not student.user.has_usable_password()

        # Check associated academic records
        assert SemesterResult.objects.filter(student=student, semester=1).exists()
        assert Result.objects.filter(student=student, semester=1).count() == 2
        assert HabitCheckInLog.objects.filter(student=student).exists()


@pytest.mark.django_db
def test_behavioral_telemetry_anti_leakage_independence():
    """
    Verify anti-leakage property: behavioral telemetry fields (hours studied, sleep, attendance)
    are independent across student results and not coupled deterministically to SGPA or percentages.
    """
    results = [SemesterResultFactory.create(sgpa=8.0, percentage=80.0) for _ in range(5)]
    study_hours = [r.hours_studied_per_week for r in results]
    sleep_hours = [r.sleep_hours_per_night for r in results]
    attendance = [r.attendance_percentage for r in results]

    # Telemetry should vary even when SGPA/percentage are identical
    assert len(set(study_hours)) > 1, "Study hours should not be constant or derived from SGPA"
    assert len(set(sleep_hours)) > 1, "Sleep hours should not be constant or derived from SGPA"
    assert len(set(attendance)) > 1, "Attendance should not be constant or derived from SGPA"
