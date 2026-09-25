"""
Test suite for EduPulse Scoped Analytics API Family (/api/v1/analytics/).
Verifies:
- Default-deny authentication and role capabilities
- Server-derived academic scope isolation and 403 on out-of-scope filters
- Breakdown hierarchy (only levels below scope permitted)
- Differential privacy: groups < 10 merged into 'Other (hidden)'
- Executive aggregate-only guarantee (zero student identifiers)
- Score distribution fixed bins in a single query
- At-risk roster pagination and faculty-only access
- CSV export, 5/hour throttling, and immutable ExportAuditLog creation
- Legacy /analytics/api/cohort-query/ endpoint retirement (404)
- Bounded query counts via django_assert_max_num_queries
"""

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from academics.models import (
    Batch,
    Course,
    Department,
    Result,
    School,
    SemesterResult,
    StudentProfile,
    Subject,
    TeachingAssignment,
)
from analytics.models import ExportAuditLog
from predictions.models import ModelVersion, PredictionSnapshot
from tests.factories import (
    AdminUserFactory,
    BatchFactory,
    ControllerUserFactory,
    CourseFactory,
    DeanUserFactory,
    DepartmentFactory,
    HODUserFactory,
    RegistrarUserFactory,
    ResultFactory,
    SchoolFactory,
    SemesterResultFactory,
    StudentProfileFactory,
    StudentUserFactory,
    SubjectFactory,
    TeacherProfileFactory,
    TeacherUserFactory,
    TeachingAssignmentFactory,
    VCUserFactory,
    make_university,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def active_model_fixture():
    mv, _ = ModelVersion.objects.get_or_create(
        slot="baseline",
        version=1,
        defaults={
            "trained_on": "test_institutional_data",
            "n_train_rows": 500,
            "n_test_rows": 100,
            "metrics": {"rmse": 3.8, "r2": 0.78, "algorithm": "GradientBoostingRegressor"},
            "feature_names": ["attendance_percentage", "internal_marks"],
            "sklearn_version": "1.6.0",
            "python_version": "3.12",
            "data_fingerprint": "hash123",
            "artifact_file": "baseline_v1.joblib",
            "is_active": True,
        },
    )
    if not mv.is_active:
        mv.is_active = True
        mv.save()
    return mv


# ============================================================================
# 1. Authentication & Capability Access Matrix Tests
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsAuthAndCapabilities:
    """Verifies default-deny security and capabilities enforcement across all analytics endpoints."""

    def test_unauthenticated_requests_return_401_or_403(self, api_client):
        endpoints = [
            reverse("api_v1:analytics-overview"),
            reverse("api_v1:analytics-breakdown") + "?by=department",
            reverse("api_v1:analytics-trend") + "?metric=pass_rate",
            reverse("api_v1:analytics-distribution") + "?subject=1",
            reverse("api_v1:analytics-at-risk"),
            reverse("api_v1:analytics-export-at-risk"),
        ]
        for url in endpoints:
            response = api_client.get(url)
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ), f"Expected 401/403 for unauthenticated request to {url}, got {response.status_code}"

    def test_student_forbidden_on_all_analytics_endpoints(self, api_client):
        tree = make_university(students_per_batch=2)
        student_user = tree["students"][0].user
        api_client.force_login(student_user)

        endpoints = [
            reverse("api_v1:analytics-overview"),
            reverse("api_v1:analytics-breakdown") + "?by=batch",
            reverse("api_v1:analytics-trend") + "?metric=pass_rate",
            reverse("api_v1:analytics-distribution") + f"?subject={tree['subjects'][0].id}",
            reverse("api_v1:analytics-at-risk"),
            reverse("api_v1:analytics-export-at-risk"),
        ]
        for url in endpoints:
            response = api_client.get(url)
            assert (
                response.status_code == status.HTTP_403_FORBIDDEN
            ), f"Student should receive 403 on {url}, got {response.status_code}"

    def test_system_admin_forbidden_on_student_analytics(self, api_client):
        tree = make_university(students_per_batch=2)
        admin_user = tree["executives"]["admin"]
        api_client.force_login(admin_user)

        endpoints = [
            reverse("api_v1:analytics-overview"),
            reverse("api_v1:analytics-breakdown") + "?by=school",
            reverse("api_v1:analytics-trend") + "?metric=pass_rate",
            reverse("api_v1:analytics-at-risk"),
        ]
        for url in endpoints:
            response = api_client.get(url)
            assert (
                response.status_code == status.HTTP_403_FORBIDDEN
            ), f"System Admin should receive 403 on {url}, got {response.status_code}"

    def test_teacher_allowed_overview_but_forbidden_at_risk_and_export(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        teacher_user = tree["teachers"][0].user
        api_client.force_login(teacher_user)

        # Teacher has view_class_analytics: overview is allowed
        resp_overview = api_client.get(reverse("api_v1:analytics-overview"))
        assert resp_overview.status_code == status.HTTP_200_OK

        # Teacher does NOT have view_at_risk_roster: at-risk is forbidden
        resp_at_risk = api_client.get(reverse("api_v1:analytics-at-risk"))
        assert resp_at_risk.status_code == status.HTTP_403_FORBIDDEN

        # Teacher does NOT have export_department/school_roster: export is forbidden
        resp_export = api_client.get(reverse("api_v1:analytics-export-at-risk"))
        assert resp_export.status_code == status.HTTP_403_FORBIDDEN

    def test_executive_allowed_aggregates_but_forbidden_at_risk_roster_and_export(
        self, api_client, active_model_fixture
    ):
        tree = make_university(students_per_batch=2)
        vc_user = tree["executives"]["vc"]
        api_client.force_login(vc_user)

        # Executive has view_executive_analytics: overview and breakdown are allowed
        resp_overview = api_client.get(reverse("api_v1:analytics-overview"))
        assert resp_overview.status_code == status.HTTP_200_OK

        # Executive receives aggregates only: at-risk roster is forbidden (HTTP 403)
        resp_at_risk = api_client.get(reverse("api_v1:analytics-at-risk"))
        assert resp_at_risk.status_code == status.HTTP_403_FORBIDDEN

        # Executive cannot export student rosters: forbidden (HTTP 403)
        resp_export = api_client.get(reverse("api_v1:analytics-export-at-risk"))
        assert resp_export.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_and_dean_allowed_at_risk_and_export(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        hod_user = tree["hod"]
        dean_user = tree["dean"]

        # HOD
        api_client.force_login(hod_user)
        assert api_client.get(reverse("api_v1:analytics-at-risk")).status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-export-at-risk")).status_code == status.HTTP_200_OK

        # Dean
        api_client.force_login(dean_user)
        assert api_client.get(reverse("api_v1:analytics-at-risk")).status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-export-at-risk")).status_code == status.HTTP_200_OK


# ============================================================================
# 2. Scope Enforcement & Out-of-Scope Filter Protection
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsScopeEnforcement:
    """Verifies server-derived scope boundaries and 403 on out-of-scope filters."""

    def test_teacher_out_of_scope_batch_filter_returns_403(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        teacher_user = tree["teachers"][0].user
        api_client.force_login(teacher_user)

        # Another batch that teacher is not assigned to
        other_batch = BatchFactory.create(course=tree["course"])

        url = reverse("api_v1:analytics-overview") + f"?batch={other_batch.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_out_of_scope_department_filter_returns_403(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)

        other_dept = DepartmentFactory.create(school=tree["school"])

        url = reverse("api_v1:analytics-overview") + f"?department={other_dept.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dean_out_of_scope_school_filter_returns_403(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        dean_user = tree["dean"]
        api_client.force_login(dean_user)

        other_school = SchoolFactory.create(university=tree["university"])

        url = reverse("api_v1:analytics-overview") + f"?school={other_school.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_breakdown_level_hierarchy_strictly_below_scope(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        teacher = tree["teachers"][0].user
        hod = tree["hod"]
        dean = tree["dean"]
        vc = tree["executives"]["vc"]

        # 1. Teacher can only breakdown by batch, subject
        api_client.force_login(teacher)
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=batch").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=subject").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=school").status_code == status.HTTP_403_FORBIDDEN
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=department").status_code == status.HTTP_403_FORBIDDEN
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=course").status_code == status.HTTP_403_FORBIDDEN

        # 2. HOD can breakdown by course, batch, subject, teacher; NOT school or department
        api_client.force_login(hod)
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=course").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=batch").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=school").status_code == status.HTTP_403_FORBIDDEN
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=department").status_code == status.HTTP_403_FORBIDDEN

        # 3. Dean can breakdown by department, course, batch, subject, teacher; NOT school
        api_client.force_login(dean)
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=department").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=school").status_code == status.HTTP_403_FORBIDDEN

        # 4. Executive can breakdown by any level
        api_client.force_login(vc)
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=school").status_code == status.HTTP_200_OK
        assert api_client.get(reverse("api_v1:analytics-breakdown") + "?by=department").status_code == status.HTTP_200_OK


# ============================================================================
# 3. Overview Endpoint & Bounded Query Budget
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsOverview:
    """Verifies KPI computation and query bounds."""

    def test_overview_kpis_and_active_model(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=12)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)

        url = reverse("api_v1:analytics-overview")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert data["total_students"] == 12
        assert "pass_rate" in data
        assert "average_percentage" in data
        assert "at_risk_count" in data
        assert "at_risk_rate" in data
        assert data["published_share"] == 100.0

        # Model data
        assert data["model"] is not None
        assert data["model"]["slot"] == "baseline"
        assert data["model"]["version"] == 1
        assert data["model"]["is_active"] is True

    def test_overview_query_budget(self, api_client, active_model_fixture, django_assert_max_num_queries):
        tree = make_university(students_per_batch=8)
        vc_user = tree["executives"]["vc"]
        api_client.force_login(vc_user)

        url = reverse("api_v1:analytics-overview")
        # Ensure queries are tightly bounded (no N+1 loops)
        with django_assert_max_num_queries(10):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK


# ============================================================================
# 4. Breakdown & Differential Privacy (ANALYTICS_MIN_GROUP_SIZE = 10)
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsBreakdownAndPrivacy:
    """Verifies differential privacy aggregation and Executive aggregate-only guarantee."""

    def test_differential_privacy_masks_groups_under_min_size(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=12)
        dean_user = tree["dean"]
        dept = tree["department"]

        # Create Course A with 12 students (>= 10: visible)
        course_a = tree["course"]

        # Create Course B with 3 students (< 10: masked)
        course_b = CourseFactory.create(name="Course Small 1", code="CS1", department=dept)
        batch_b = BatchFactory.create(course=course_b, strength=3)
        for i in range(3):
            st = StudentProfileFactory.create(course=course_b, batch=batch_b)
            SemesterResultFactory.create(student=st, semester=1, percentage=60.0, is_published=True)

        # Create Course C with 4 students (< 10: masked)
        course_c = CourseFactory.create(name="Course Small 2", code="CS2", department=dept)
        batch_c = BatchFactory.create(course=course_c, strength=4)
        for i in range(4):
            st = StudentProfileFactory.create(course=course_c, batch=batch_c)
            SemesterResultFactory.create(student=st, semester=1, percentage=70.0, is_published=True)

        api_client.force_login(dean_user)
        url = reverse("api_v1:analytics-breakdown") + "?by=course"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        groups = data["groups"]
        group_names = [g["name"] for g in groups]

        # Course A must be visible
        assert course_a.name in group_names

        # Course B and Course C must NOT be visible individually
        assert course_b.name not in group_names
        assert course_c.name not in group_names

        # An 'Other (hidden)' group must exist combining them (3 + 4 = 7 students)
        assert "Other (hidden)" in group_names
        other_group = next(g for g in groups if g["name"] == "Other (hidden)")
        assert other_group["student_count"] == 7
        assert other_group["id"] is None
        assert other_group["code"] == "OTHER"

    def test_executive_response_contains_zero_student_pii(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=15)
        vc_user = tree["executives"]["vc"]
        api_client.force_login(vc_user)

        url = reverse("api_v1:analytics-breakdown") + "?by=department"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_str = str(response.content)

        # Assert no student roll numbers or student names appear
        for student in tree["students"]:
            assert student.roll_no not in response_str
            assert student.user.username not in response_str


# ============================================================================
# 5. Longitudinal Trend & Distribution Endpoints
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsTrendAndDistribution:
    """Verifies trend points per semester and fixed-bin histogram distribution."""

    def test_trend_pass_rate_and_avg_percentage(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=6)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)

        # Add semester 2 results
        for st in tree["students"]:
            SemesterResultFactory.create(student=st, semester=2, percentage=75.0, sgpa=7.5, is_published=True)

        url = reverse("api_v1:analytics-trend") + "?metric=pass_rate"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["metric"] == "pass_rate"
        points = response.data["points"]
        assert len(points) >= 2
        assert points[0]["semester"] == 1
        assert points[1]["semester"] == 2

    def test_trend_invalid_metric_returns_400(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)

        url = reverse("api_v1:analytics-trend") + "?metric=invalid_metric"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_distribution_returns_fixed_bins_in_single_query(
        self, api_client, active_model_fixture, django_assert_max_num_queries
    ):
        tree = make_university(students_per_batch=10)
        hod_user = tree["hod"]
        subject = tree["subjects"][0]
        api_client.force_login(hod_user)

        url = reverse("api_v1:analytics-distribution") + f"?subject={subject.id}"
        with django_assert_max_num_queries(8):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["subject"]["id"] == subject.id
        assert data["subject"]["code"] == subject.code
        assert len(data["bins"]) == 7
        labels = [b["label"] for b in data["bins"]]
        assert labels == ["<40%", "40-49%", "50-59%", "60-69%", "70-79%", "80-89%", "90-100%"]

    def test_distribution_out_of_scope_subject_returns_403(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)

        # Subject in another department
        other_dept = DepartmentFactory.create(school=tree["school"])
        other_course = CourseFactory.create(department=other_dept)
        other_sub = SubjectFactory.create(course=other_course)

        url = reverse("api_v1:analytics-distribution") + f"?subject={other_sub.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 6. At-Risk Roster & Audit Log CSV Export
# ============================================================================

@pytest.mark.django_db
class TestAtRiskRosterAndExport:
    """Verifies at-risk student pagination, CSV download, audit logging, and rate limiting."""

    def test_at_risk_roster_paginated_and_scoped_to_department(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=4)
        hod_user = tree["hod"]
        students = tree["students"]
        subject = tree["subjects"][0]

        # Create snapshots: 2 at-risk, 2 low risk
        for i, st in enumerate(students):
            risk = "high" if i < 2 else "low"
            score = 32.0 if i < 2 else 72.0
            PredictionSnapshot.objects.create(
                student=st,
                subject=subject,
                semester=1,
                checkpoint="midterm",
                model_version=active_model_fixture,
                predicted_percentage=score,
                risk_band=risk,
                reasons=["Low attendance"] if i < 2 else [],
                taken_at=timezone.now(),
            )

        api_client.force_login(hod_user)
        url = reverse("api_v1:analytics-at-risk")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert "count" in data
        assert data["count"] == 2
        results = data["results"]
        assert len(results) == 2
        assert all(r["risk_band"] == "high" for r in results)

    def test_export_csv_creates_audit_log_without_pii(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=3)
        hod_user = tree["hod"]
        student = tree["students"][0]
        subject = tree["subjects"][0]

        PredictionSnapshot.objects.create(
            student=student,
            subject=subject,
            semester=1,
            checkpoint="midterm",
            model_version=active_model_fixture,
            predicted_percentage=35.0,
            risk_band="high",
            reasons=["Attendance deficit"],
            taken_at=timezone.now(),
        )

        api_client.force_login(hod_user)
        url = reverse("api_v1:analytics-export-at-risk")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "attachment; filename=\"at_risk_roster.csv\"" in response["Content-Disposition"]

        content = response.content.decode("utf-8")
        assert "Roll No,Name,Batch,Course,Subject,Semester,Risk Band,Predicted Percentage,Reasons,Taken At" in content
        assert student.roll_no in content

        # Verify ExportAuditLog was created
        log = ExportAuditLog.objects.filter(user=hod_user).first()
        assert log is not None
        assert log.scope_level == "department"
        assert log.row_count == 1
        assert "student" not in log.filters_applied

    def test_export_rate_throttle_enforces_limit(self, api_client, active_model_fixture):
        tree = make_university(students_per_batch=2)
        hod_user = tree["hod"]
        api_client.force_login(hod_user)
        url = reverse("api_v1:analytics-export-at-risk")

        # 5 exports per hour allowed
        for i in range(5):
            res = api_client.get(url)
            assert res.status_code == status.HTTP_200_OK, f"Request {i+1} should be 200 OK"

        # 6th export within the same hour must be throttled
        res_throttled = api_client.get(url)
        assert res_throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ============================================================================
# 7. Legacy Endpoint Retirement Test
# ============================================================================

@pytest.mark.django_db
class TestLegacyCohortQueryRetirement:
    """Verifies that legacy /analytics/api/cohort-query/ is retired and returns 404."""

    def test_legacy_cohort_query_returns_404(self, api_client):
        tree = make_university(students_per_batch=2)
        vc_user = tree["executives"]["vc"]
        api_client.force_login(vc_user)

        response = api_client.get("/analytics/api/cohort-query/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
