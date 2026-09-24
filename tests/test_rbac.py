"""
Role-Based Access Control (RBAC) and Organizational Hierarchy Scoping Tests.
Tests current baseline permissions for all 8 institutional roles across all application routes.
"""
import pytest
from django.urls import reverse
from academics.models import Result
from accounts.views import scoped_results_for
from tests.factories import (
    make_university,
    StudentUserFactory,
    TeacherUserFactory,
    HODUserFactory,
    DeanUserFactory,
    VCUserFactory,
    RegistrarUserFactory,
    ControllerUserFactory,
    AdminUserFactory,
)


# List of all 11 routes in accounts/urls.py
ALL_ACCOUNT_ROUTES = [
    "index",
    "home",
    "analytics_hub",
    "api_cohort_query",
    "my_results",
    "scoped_results",
    "my_predictions",
    "at_risk_students",
    "teacher_internal_marks",
    "habit_checkin",
    "update_habit_preference",
]


# ---------------------------------------------------------------------------
# 1. UNAUTHENTICATED ACCESS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ALL_ACCOUNT_ROUTES)
def test_unauthenticated_requests_redirect_to_login(client, route_name):
    """Anonymous requests to any route must be redirected (HTTP 302) to the login screen."""
    url = reverse(route_name)
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


# ---------------------------------------------------------------------------
# 2. PARAMETRIZED RBAC MATRIX (CURRENT STATUS CODES)
# ---------------------------------------------------------------------------

# Baseline HTTP status code matrix for each role across all 11 routes:
# Format: (role, route_name, expected_status)
RBAC_MATRIX = []

ROLES = [
    "STUDENT",
    "TEACHER",
    "HOD",
    "DEAN",
    "VC",
    "REGISTRAR",
    "CONTROLLER_OF_EXAMS",
]

for role in ROLES:
    for route in ALL_ACCOUNT_ROUTES:
        if route == "index":
            # index always redirects to login
            expected = 302
        elif route == "update_habit_preference":
            # update_habit_preference is POST-only; GET redirects
            expected = 302
        elif route == "teacher_internal_marks":
            # Only teachers with a profile can GET teacher_internal_marks (others redirect to home)
            expected = 200 if role == "TEACHER" else 302
        elif route == "habit_checkin":
            # Only students have a student_profile to check in; others redirect to home
            expected = 200 if role == "STUDENT" else 302
        else:
            # All other routes currently return 200 for authenticated roles
            expected = 200
        RBAC_MATRIX.append((role, route, expected))


@pytest.mark.django_db
@pytest.mark.parametrize("role,route_name,expected_status", RBAC_MATRIX)
def test_rbac_matrix_status_codes(client, role, route_name, expected_status):
    """
    Verify current HTTP status codes across all 8 roles and all application routes.
    Pins current behavior as a regression baseline.
    """
    tree = make_university(students_per_batch=2)
    users_by_role = {
        "STUDENT": tree["students"][0].user,
        "TEACHER": tree["teachers"][0].user,
        "HOD": tree["hod"],
        "DEAN": tree["dean"],
        "VC": tree["executives"]["vc"],
        "REGISTRAR": tree["executives"]["registrar"],
        "CONTROLLER_OF_EXAMS": tree["executives"]["controller"],
    }
    user = users_by_role[role]
    client.force_login(user)

    url = reverse(route_name)
    response = client.get(url)
    assert response.status_code == expected_status, (
        f"Role {role} accessing {route_name} expected HTTP {expected_status}, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# 3. ORGANIZATIONAL SCOPE TESTS (scoped_results_for)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_scoped_results_for_teacher():
    """A teacher must only see results for students in subjects they teach."""
    tree = make_university(students_per_batch=4)
    teacher1_user = tree["teachers"][0].user
    teacher2_user = tree["teachers"][1].user

    t1_results, label1 = scoped_results_for(teacher1_user)
    assert t1_results.count() == 4
    for res in t1_results:
        assert res.teacher == tree["teachers"][0]

    t2_results, label2 = scoped_results_for(teacher2_user)
    assert t2_results.count() == 4
    for res in t2_results:
        assert res.teacher == tree["teachers"][1]


@pytest.mark.django_db
def test_scoped_results_for_hod():
    """An HOD must only see results for courses/departments within their department."""
    tree = make_university(students_per_batch=4)
    hod_user = tree["hod"]

    results, label = scoped_results_for(hod_user)
    # 4 students * 2 subjects = 8 results in this department
    assert results.count() == 8
    for res in results:
        assert res.subject.course.department == tree["department"]


@pytest.mark.django_db
def test_scoped_results_for_dean():
    """A Dean must only see results within their school."""
    tree = make_university(students_per_batch=4)
    dean_user = tree["dean"]

    results, label = scoped_results_for(dean_user)
    assert results.count() == 8
    for res in results:
        assert res.subject.course.department.school == tree["school"]


@pytest.mark.django_db
def test_scoped_results_for_student():
    """A student must have no access to bulk scoped results."""
    tree = make_university(students_per_batch=2)
    student_user = tree["students"][0].user

    results, label = scoped_results_for(student_user)
    assert results.count() == 0
    assert label == "No access"


@pytest.mark.django_db
def test_scoped_results_for_executives():
    """Executives (VC, Registrar, Controller of Exams, System Admin) see all university results."""
    tree = make_university(students_per_batch=3)
    # Total results = 3 students * 2 subjects = 6
    total_count = Result.objects.count()

    for role_key in ("vc", "registrar", "controller", "admin"):
        exec_user = tree["executives"][role_key]
        results, label = scoped_results_for(exec_user)
        assert results.count() == total_count
        assert label == "Entire University"
