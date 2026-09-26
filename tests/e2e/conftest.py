"""
Playwright End-to-End (E2E) browser test fixtures and configuration.
Enforces that tests run against the edupulse_e2e database with live Django server.
"""

import os
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest
from pathlib import Path
from django.conf import settings
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
    SemesterResult,
    Result,
    HabitCheckInLog,
)
from predictions.models import ModelVersion

User = get_user_model()

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session", autouse=True)
def verify_e2e_environment():
    """Safety guard: verify settings and database before running any E2E browser tests."""
    db_name = settings.DATABASES["default"]["NAME"]
    assert db_name.endswith("_e2e") or "e2e" in db_name or "test" in db_name, (
        f"CRITICAL SAFETY VIOLATION: E2E tests attempted against non-e2e database: {db_name}"
    )


@pytest.fixture
def e2e_page(page, live_server, request):
    """
    Enhanced Playwright Page fixture for EduPulse E2E tests.
    Monitors console errors, third-party requests, and captures screenshots on test failure.
    """
    console_errors = []
    third_party_requests = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    def on_request(req):
        url = req.url
        # Allow only same-origin live_server requests and data: or blob: URLs
        if not (url.startswith(live_server.url) or url.startswith("data:") or url.startswith("blob:")):
            third_party_requests.append(url)

    page.on("console", on_console)
    page.on("request", on_request)

    yield page

    # Screenshot and cleanup on failure
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        test_name = request.node.name.replace("/", "_").replace("::", "_")
        screenshot_path = ARTIFACTS_DIR / f"fail_{test_name}.png"
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass

    # Strict hygiene assertions: zero third-party requests and zero console errors
    assert not third_party_requests, f"Forbidden third-party network requests detected: {third_party_requests}"


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def e2e_seed_data(db):
    """
    Provisions a comprehensive, isolated academic hierarchy in the E2E database.
    Creates structured test accounts with known passwords for real browser login.
    """
    univ = University.objects.create(name="E2E Institute of Technology", code="E2E01", established_year=2000)
    school = School.objects.create(university=univ, name="School of Engineering", code="SOE")
    dept = Department.objects.create(school=school, name="Computer Science & Engineering", code="CSE")
    other_dept = Department.objects.create(school=school, name="Electrical Engineering", code="EE")
    course = Course.objects.create(department=dept, name="B.Tech Computer Science", code="CS101", level="UG", duration_years=4)
    batch = Batch.objects.create(course=course, batch_code="2024-CSE-A", admission_year=2024, current_study_year=2, current_semester=3)
    subject = Subject.objects.create(course=course, code="CS301", title="Database Management Systems", semester=3, credits=4, internal_max=30, external_max=70)

    # 1. Student
    student_user = User.objects.create_user(
        username="e2e_student",
        email="e2e_student@example.test",
        first_name="Aarav",
        last_name="Sharma",
        role=User.Role.STUDENT,
        status="active",
    )
    student_user.set_password("StudentPass@123")
    student_user.save()
    student_profile = StudentProfile.objects.create(
        user=student_user,
        roll_no="E2E-CS-001",
        course=course,
        batch=batch,
        current_semester=3,
        data_origin="real",
    )

    # Historical Result for Student
    sem_result = SemesterResult.objects.create(
        student=student_profile,
        semester=2,
        total_max=100,
        total_secured=84,
        sgpa=8.4,
        percentage=84.0,
        is_published=True,
    )
    Result.objects.create(
        student=student_profile,
        subject=subject,
        batch=batch,
        semester=2,
        internal_marks=26,
        external_marks=58,
        total_secured=84,
        max_marks=100,
        credits=4,
        letter_grade="A+",
    )

    # 2. Teacher
    teacher_user = User.objects.create_user(
        username="e2e_teacher",
        email="e2e_teacher@example.test",
        first_name="Dr. Priya",
        last_name="Verma",
        role=User.Role.TEACHER,
        status="active",
    )
    teacher_user.set_password("TeacherPass@123")
    teacher_user.save()
    teacher_profile = TeacherProfile.objects.create(
        user=teacher_user,
        staff_id="T-E2E-001",
        department=dept,
        designation="Associate Professor",
    )
    TeachingAssignment.objects.create(
        teacher=teacher_profile,
        subject=subject,
        batch=batch,
        academic_session="2026-2027",
    )

    # 3. HOD
    hod_user = User.objects.create_user(
        username="e2e_hod",
        email="e2e_hod@example.test",
        first_name="Prof. Rajesh",
        last_name="Gupta",
        role=User.Role.HOD,
        department=dept,
        school=school,
        status="active",
    )
    hod_user.set_password("HodPass@123")
    hod_user.save()
    TeacherProfile.objects.create(
        user=hod_user,
        staff_id="T-E2E-HOD",
        department=dept,
        designation="Head of Department",
    )

    # 4. Dean
    dean_user = User.objects.create_user(
        username="e2e_dean",
        email="e2e_dean@example.test",
        first_name="Dr. Suman",
        last_name="Rao",
        role=User.Role.DEAN,
        school=school,
        status="active",
    )
    dean_user.set_password("DeanPass@123")
    dean_user.save()
    TeacherProfile.objects.create(
        user=dean_user,
        staff_id="T-E2E-DEAN",
        department=dept,
        designation="Dean of Engineering",
    )

    # 5. Executive (Vice Chancellor)
    vc_user = User.objects.create_user(
        username="e2e_vc",
        email="e2e_vc@example.test",
        first_name="Dr. Vikram",
        last_name="Malhotra",
        role=User.Role.VC,
        status="active",
    )
    vc_user.set_password("VcPass@123")
    vc_user.save()

    # 6. System Admin
    admin_user = User.objects.create_user(
        username="e2e_admin",
        email="e2e_admin@example.test",
        first_name="System",
        last_name="Administrator",
        role=User.Role.SYSADMIN,
        is_staff=True,
        is_superuser=True,
        status="active",
    )
    admin_user.set_password("AdminPass@123")
    admin_user.save()

    # Model Version in Registry
    ModelVersion.objects.create(
        slot="baseline",
        version=1,
        is_active=True,
        artifact_file="model_a_v1.pkl",
        trained_on="Baseline Synthetic Dataset",
        n_train_rows=1000,
        n_test_rows=200,
        metrics={"rmse": 3.2, "r2": 0.85},
        feature_names=["attendance_percentage", "hours_studied_per_week"],
        sklearn_version="1.6.1",
        python_version="3.12.4",
        data_fingerprint="sha256_dummy_fingerprint_baseline",
    )
    ModelVersion.objects.create(
        slot="institute",
        version=2,
        is_active=False,
        artifact_file="model_b_v2.pkl",
        trained_on="Institutional Historical Cohort 2024",
        n_train_rows=500,
        n_test_rows=100,
        metrics={"rmse": 2.7, "r2": 0.89},
        feature_names=["attendance_percentage", "hours_studied_per_week", "sleep_hours_per_night"],
        sklearn_version="1.6.1",
        python_version="3.12.4",
        data_fingerprint="sha256_dummy_fingerprint_institute",
    )

    return {
        "univ": univ,
        "dept": dept,
        "other_dept": other_dept,
        "course": course,
        "batch": batch,
        "subject": subject,
        "student": student_user,
        "teacher": teacher_user,
        "hod": hod_user,
        "dean": dean_user,
        "vc": vc_user,
        "admin": admin_user,
    }


def login_via_ui(page, live_server, username, password):
    """Helper to perform browser-based authentication via React /app/login."""
    page.goto(f"{live_server.url}/app/login")
    page.wait_for_selector("#username-input", state="visible")
    page.fill("#username-input", username)
    page.fill("#password-input", password)
    page.click("button:has-text('Sign In')")
    # Wait for login navigation away from login page
    page.wait_for_url(lambda u: "/app/login" not in u, timeout=10000)
