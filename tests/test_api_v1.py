"""
Comprehensive test suite for EduPulse Core REST API (/api/v1/).
Verifies:
- Session auth, login, logout, and CSRF protection
- Table-driven capabilities per role from docs/ROLES_AND_FEATURES.md
- Granular RBAC endpoint matrix
- Object-level scope isolation on student results & predictions
- Habit check-in range validation & streak mechanics
- Bulk internal marks atomic validation & per-row error reporting
- Model registry access control
- Uniform error JSON shape {code, detail, fields}
"""

import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from accounts.permissions import ROLE_CAPABILITIES, capabilities_for
from academics.models import (
    Result,
    SemesterResult,
    HabitCheckInLog,
    StudentHabitPreference,
    TeachingAssignment,
)
from predictions.models import ModelVersion

from .factories import (
    StudentUserFactory,
    TeacherUserFactory,
    HODUserFactory,
    DeanUserFactory,
    VCUserFactory,
    RegistrarUserFactory,
    ControllerUserFactory,
    AdminUserFactory,
    SchoolFactory,
    DepartmentFactory,
    CourseFactory,
    BatchFactory,
    SubjectFactory,
    StudentProfileFactory,
    TeacherProfileFactory,
    TeachingAssignmentFactory,
    SemesterResultFactory,
    ResultFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


# ============================================================================
# 1. CSRF & Authentication Tests
# ============================================================================

@pytest.mark.django_db
class TestAuthAndCSRF:
    def test_get_csrf_token(self, api_client):
        """GET /api/v1/csrf/ returns a valid csrfToken."""
        url = reverse("api_v1:csrf")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "csrfToken" in response.data
        assert len(response.data["csrfToken"]) > 10

    def test_login_success(self, api_client):
        """Successful login returns user identity, capabilities, and creates session."""
        user = StudentUserFactory(username="test_student", email="student@example.test")
        user.set_password("CorrectPassword123!")
        user.save()
        StudentProfileFactory(user=user)

        url = reverse("api_v1:login")
        response = api_client.post(
            url,
            {"username": "test_student", "password": "CorrectPassword123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == user.id
        assert data["role"] == "STUDENT"
        assert "capabilities" in data
        assert "view_own_results" in data["capabilities"]
        # Assert NO email or phone in response
        assert "email" not in data
        assert "phone" not in data

    def test_login_invalid_credentials_returns_generic_error(self, api_client):
        """Invalid credentials return 400 with uniform error shape and generic message."""
        user = StudentUserFactory(username="test_student")
        user.set_password("CorrectPassword123!")
        user.save()

        url = reverse("api_v1:login")
        response = api_client.post(
            url,
            {"username": "test_student", "password": "WrongPassword!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "authentication_failed"
        assert response.data["detail"] == "Invalid username or password."
        assert response.data["fields"] == {}

    def test_login_inactive_user_rejected(self, api_client):
        """Inactive user account cannot authenticate."""
        user = StudentUserFactory(username="inactive_user", is_active=False)
        user.set_password("ValidPassword123!")
        user.save()

        url = reverse("api_v1:login")
        response = api_client.post(
            url,
            {"username": "inactive_user", "password": "ValidPassword123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "authentication_failed"

    def test_logout_terminates_session(self, api_client):
        """POST /api/v1/auth/logout/ invalidates session."""
        user = StudentUserFactory()
        api_client.force_authenticate(user=user)

        url = reverse("api_v1:logout")
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Successfully logged out."

    def test_csrf_failure_on_unsafe_request(self):
        """Session-authenticated request without CSRF token fails with 403 Forbidden."""
        user = StudentUserFactory(username="csrf_test_user")
        user.set_password("SecurePassword123!")
        user.save()

        client = APIClient(enforce_csrf_checks=True)
        logged_in = client.login(username="csrf_test_user", password="SecurePassword123!")
        assert logged_in is True

        # An unsafe POST to logout without X-CSRFToken header must fail with 403
        logout_url = reverse("api_v1:logout")
        response = client.post(logout_url, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == "permission_denied"
        assert "CSRF" in response.data["detail"]


# ============================================================================
# 2. Table-Driven Capabilities per Role Tests
# ============================================================================

@pytest.mark.django_db
class TestCapabilitiesPerRole:
    @pytest.mark.parametrize(
        "role_code,factory_cls,expected_caps",
        [
            (
                "STUDENT",
                StudentUserFactory,
                [
                    "view_own_results",
                    "view_own_predictions",
                    "submit_habit_checkin",
                    "view_own_habits",
                ],
            ),
            (
                "TEACHER",
                TeacherUserFactory,
                [
                    "view_class_analytics",
                    "enter_internal_marks",
                    "export_class_roster",
                    "view_teaching_assignments",
                ],
            ),
            (
                "HOD",
                HODUserFactory,
                [
                    "view_department_analytics",
                    "view_at_risk_roster",
                    "export_department_roster",
                ],
            ),
            (
                "DEAN",
                DeanUserFactory,
                [
                    "view_school_analytics",
                    "view_at_risk_roster",
                    "export_school_roster",
                ],
            ),
            ("VC", VCUserFactory, ["view_executive_analytics"]),
            ("REGISTRAR", RegistrarUserFactory, ["view_executive_analytics"]),
            ("CONTROLLER_OF_EXAMS", ControllerUserFactory, ["view_executive_analytics"]),
            (
                "SYSTEM_ADMIN",
                AdminUserFactory,
                ["manage_models", "view_system_health", "access_admin"],
            ),
        ],
    )
    def test_role_capabilities_matrix(self, api_client, role_code, factory_cls, expected_caps):
        """GET /api/v1/me/ returns exact capabilities mandated by docs/ROLES_AND_FEATURES.md."""
        user = factory_cls()
        api_client.force_authenticate(user=user)

        url = reverse("api_v1:me")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        returned_caps = response.data["capabilities"]
        assert sorted(returned_caps) == sorted(expected_caps)
        assert response.data["role"] == role_code
        # PII Quarantine
        assert "email" not in response.data
        assert "phone" not in response.data


# ============================================================================
# 3. Scope Isolation on Academic Results & Predictions
# ============================================================================

@pytest.mark.django_db
class TestScopeIsolation:
    def test_student_can_view_own_results(self, api_client):
        """Student requesting their own results receives 200 OK."""
        user = StudentUserFactory()
        student = StudentProfileFactory(user=user)
        SemesterResultFactory(student=student, semester=1, is_published=True)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:student-results", kwargs={"id": student.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["student_id"] == student.id
        assert len(response.data["semester_results"]) == 1

    def test_student_cannot_view_other_student_results(self, api_client):
        """Student requesting another student's results receives 403 Forbidden."""
        user1 = StudentUserFactory()
        student1 = StudentProfileFactory(user=user1)

        user2 = StudentUserFactory()
        student2 = StudentProfileFactory(user=user2)

        api_client.force_authenticate(user=user1)
        url = reverse("api_v1:student-results", kwargs={"id": student2.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == "permission_denied"

    def test_student_cannot_view_other_student_predictions(self, api_client):
        """Student requesting another student's predictions receives 403 Forbidden."""
        user1 = StudentUserFactory()
        StudentProfileFactory(user=user1)

        user2 = StudentUserFactory()
        student2 = StudentProfileFactory(user=user2)

        api_client.force_authenticate(user=user1)
        url = reverse("api_v1:student-predictions", kwargs={"id": student2.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_teacher_scope_isolation_on_results(self, api_client):
        """Teacher can view students in assigned batches, but receives 403 on unassigned batches."""
        teacher_user = TeacherUserFactory()
        teacher = TeacherProfileFactory(user=teacher_user)

        batch_taught = BatchFactory()
        batch_other = BatchFactory()

        student_in_class = StudentProfileFactory(batch=batch_taught)
        student_other = StudentProfileFactory(batch=batch_other)

        # Assign teacher to batch_taught
        TeachingAssignmentFactory(teacher=teacher, batch=batch_taught)

        api_client.force_authenticate(user=teacher_user)

        # Assigned batch student -> 200 OK
        url_taught = reverse("api_v1:student-results", kwargs={"id": student_in_class.id})
        res_taught = api_client.get(url_taught)
        assert res_taught.status_code == status.HTTP_200_OK

        # Unassigned batch student -> 403 Forbidden
        url_other = reverse("api_v1:student-results", kwargs={"id": student_other.id})
        res_other = api_client.get(url_other)
        assert res_other.status_code == status.HTTP_403_FORBIDDEN

    def test_executive_refused_student_level_results(self, api_client):
        """Executives (VC) see aggregates only and receive 403 on per-student result queries."""
        vc_user = VCUserFactory()
        student = StudentProfileFactory()

        api_client.force_authenticate(user=vc_user)
        url = reverse("api_v1:student-results", kwargs={"id": student.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 4. Habit Check-In Tests
# ============================================================================

@pytest.mark.django_db
class TestHabitCheckIns:
    def test_valid_daily_checkin(self, api_client):
        """Valid daily check-in is saved and streak is incremented."""
        user = StudentUserFactory()
        student = StudentProfileFactory(user=user)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:habit-checkins")
        payload = {
            "log_type": "DAILY",
            "hours_studied": 4.5,
            "sleep_hours": 7.5,
            "motivation_level": "HIGH",
            "tutoring_sessions": 1,
            "physical_activity": 1.0,
            "notes": "Focused study session.",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["hours_studied"] == 4.5
        assert response.data["sleep_hours"] == 7.5

        # Check database persistence
        assert HabitCheckInLog.objects.filter(student=student).count() == 1
        pref = StudentHabitPreference.objects.get(student=student)
        assert pref.streak_count == 1

    def test_invalid_daily_study_hours_rejected(self, api_client):
        """Daily study hours > 24 is rejected with validation_error."""
        user = StudentUserFactory()
        StudentProfileFactory(user=user)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:habit-checkins")
        payload = {
            "log_type": "DAILY",
            "hours_studied": 25.0,  # Invalid (>24)
            "sleep_hours": 7.0,
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert "hours_studied" in response.data["fields"]

    def test_invalid_sleep_hours_rejected(self, api_client):
        """Sleep hours outside 0-24 is rejected with validation_error."""
        user = StudentUserFactory()
        StudentProfileFactory(user=user)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:habit-checkins")
        payload = {
            "log_type": "DAILY",
            "hours_studied": 4.0,
            "sleep_hours": 26.0,  # Invalid
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"


# ============================================================================
# 5. Bulk Internal Marks Tests
# ============================================================================

@pytest.mark.django_db
class TestBulkInternalMarks:
    def test_teacher_bulk_marks_success(self, api_client):
        """Assigned teacher can bulk submit valid internal marks."""
        teacher_user = TeacherUserFactory()
        teacher = TeacherProfileFactory(user=teacher_user)
        batch = BatchFactory()
        subject = SubjectFactory(internal_max=25, semester=1)

        student1 = StudentProfileFactory(batch=batch)
        student2 = StudentProfileFactory(batch=batch)

        TeachingAssignmentFactory(teacher=teacher, subject=subject, batch=batch)

        api_client.force_authenticate(user=teacher_user)
        url = reverse("api_v1:internal-marks")
        payload = {
            "subject_id": subject.id,
            "batch_id": batch.id,
            "marks": [
                {"student_id": student1.id, "internal_marks": 22},
                {"student_id": student2.id, "internal_marks": 19},
            ],
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated_count"] == 2

        # Verify Result records updated
        r1 = Result.objects.get(student=student1, subject=subject)
        r2 = Result.objects.get(student=student2, subject=subject)
        assert r1.internal_marks == 22
        assert r2.internal_marks == 19

    def test_unassigned_teacher_marks_entry_forbidden(self, api_client):
        """Teacher not assigned to subject/batch receives 403 Forbidden."""
        teacher_user = TeacherUserFactory()
        TeacherProfileFactory(user=teacher_user)
        batch = BatchFactory()
        subject = SubjectFactory(internal_max=25)
        student = StudentProfileFactory(batch=batch)

        api_client.force_authenticate(user=teacher_user)
        url = reverse("api_v1:internal-marks")
        payload = {
            "subject_id": subject.id,
            "batch_id": batch.id,
            "marks": [{"student_id": student.id, "internal_marks": 20.0}],
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == "permission_denied"

    def test_marks_exceeding_max_triggers_per_row_error_report(self, api_client):
        """Marks > subject.internal_max returns 400 per-row error report and rolls back atomically."""
        teacher_user = TeacherUserFactory()
        teacher = TeacherProfileFactory(user=teacher_user)
        batch = BatchFactory()
        subject = SubjectFactory(internal_max=25)

        student1 = StudentProfileFactory(batch=batch)
        student2 = StudentProfileFactory(batch=batch)
        TeachingAssignmentFactory(teacher=teacher, subject=subject, batch=batch)

        api_client.force_authenticate(user=teacher_user)
        url = reverse("api_v1:internal-marks")
        payload = {
            "subject_id": subject.id,
            "batch_id": batch.id,
            "marks": [
                {"student_id": student1.id, "internal_marks": 20.0},
                {"student_id": student2.id, "internal_marks": 35.0},  # Exceeds max 25!
            ],
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        marks_errors = response.data["fields"]["marks"]
        assert len(marks_errors) == 1
        assert marks_errors[0]["row"] == 2
        assert marks_errors[0]["student_id"] == student2.id

        # Verify atomic rollback: student1 was NOT updated!
        assert not Result.objects.filter(student=student1, subject=subject).exists()


# ============================================================================
# 6. Model Registry RBAC Tests
# ============================================================================

@pytest.mark.django_db
class TestModelRegistryAPI:
    def test_system_admin_can_access_models(self, api_client):
        """SYSTEM_ADMIN role can list registered models."""
        admin_user = AdminUserFactory()
        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="Test Kaggle Dataset",
            n_train_rows=800,
            n_test_rows=200,
            metrics={"rmse": 4.5, "r2": 0.72},
            feature_names=["attendance_percentage", "hours_studied"],
            is_active=True,
        )

        api_client.force_authenticate(user=admin_user)
        url = reverse("api_v1:models")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["slot"] == "baseline"

    def test_non_admin_cannot_access_models(self, api_client):
        """Student or teacher accessing model registry receives 403."""
        teacher = TeacherUserFactory()
        TeacherProfileFactory(user=teacher)

        api_client.force_authenticate(user=teacher)
        url = reverse("api_v1:models")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 7. Pagination, Query Budgets & OpenAPI Schema Tests
# ============================================================================

@pytest.mark.django_db
class TestPaginationAndQueryBudgets:
    def test_habits_pagination(self, api_client):
        """Habits list endpoint paginates at page_size=25."""
        user = StudentUserFactory()
        student = StudentProfileFactory(user=user)

        # Create 30 logs
        logs = [
            HabitCheckInLog(
                student=student,
                hours_studied=2.0,
                sleep_hours=7.0,
            )
            for _ in range(30)
        ]
        HabitCheckInLog.objects.bulk_create(logs)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:habit-checkins")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 30
        assert len(response.data["results"]) == 25
        assert response.data["next"] is not None

    def test_student_results_query_budget(self, api_client, django_assert_max_num_queries):
        """Query budget on student-results is bounded to prevent N+1 query regression."""
        user = StudentUserFactory()
        student = StudentProfileFactory(user=user)

        for sem in range(1, 4):
            SemesterResultFactory(student=student, semester=sem, is_published=True)
            for _ in range(5):
                ResultFactory(student=student, semester=sem)

        api_client.force_authenticate(user=user)
        url = reverse("api_v1:student-results", kwargs={"id": student.id})

        with django_assert_max_num_queries(10):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK


class TestOpenAPISchema:
    def test_openapi_yaml_exists_and_valid(self):
        """Validates that docs/openapi.yaml exists and schema command completes with 0 warnings."""
        from pathlib import Path
        from django.conf import settings
        from django.core.management import call_command

        yaml_path = Path(settings.BASE_DIR).parent / "docs" / "openapi.yaml"
        assert yaml_path.is_file()
        assert yaml_path.stat().st_size > 5000

        # Must execute without warnings or exceptions
        call_command("spectacular", validate=True, fail_on_warn=True)
