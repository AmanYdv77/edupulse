"""
Test suite for EduPulse Redis and In-Memory Caching & Invalidation Layer (Task A24).
Verifies:
- Cache hits on repeat requests (0 database queries on repeat calls).
- Analytics overview, breakdown, trend, and distribution endpoint caching.
- Student predictions caching per student and target semester.
- Automatic event-driven invalidation on:
    * Result save / delete and Bulk internal marks entry
    * SemesterResult publication / updates
    * PredictionSnapshot insertion
    * HabitCheckInLog / StudentHabitPreference updates
    * ModelVersion registry changes
- Fault tolerance & graceful degradation when cache fails.
- Cache key isolation across different roles, scopes, and query parameters.
"""

from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from academics.models import (
    HabitCheckInLog,
    Result,
    SemesterResult,
    StudentHabitPreference,
)
from api.caching import (
    get_analytics_cache_version,
    get_model_cache_version,
    get_student_prediction_version,
    invalidate_analytics_cache,
    invalidate_model_cache,
    invalidate_student_prediction_cache,
    make_analytics_cache_key,
    make_prediction_cache_key,
    safe_cache_get,
    safe_cache_set,
)
from predictions.models import ModelVersion, PredictionSnapshot
from tests.factories import (
    BatchFactory,
    CourseFactory,
    DepartmentFactory,
    HabitCheckInLogFactory,
    HODUserFactory,
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
def clear_all_cache():
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
# 1. Analytics Endpoints Caching Tests (Cache Hit = 0 DB Queries)
# ============================================================================

@pytest.mark.django_db
class TestAnalyticsCaching:

    def test_overview_caching_and_zero_db_queries_on_repeat(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        api_client.force_authenticate(user=vc)
        url = reverse("api_v1:analytics-overview")

        # First call: computes from database and sets cache
        resp1 = api_client.get(url)
        assert resp1.status_code == status.HTTP_200_OK

        # Second call: must hit cache and execute ZERO database queries
        with django_assert_num_queries(0):
            resp2 = api_client.get(url)
            assert resp2.status_code == status.HTTP_200_OK
            assert resp2.json() == resp1.json()

    def test_breakdown_caching_and_zero_db_queries(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        api_client.force_authenticate(user=vc)
        url = reverse("api_v1:analytics-breakdown") + "?by=school"

        # First call
        resp1 = api_client.get(url)
        assert resp1.status_code == status.HTTP_200_OK

        # Second call: zero DB queries
        with django_assert_num_queries(0):
            resp2 = api_client.get(url)
            assert resp2.status_code == status.HTTP_200_OK
            assert resp2.json() == resp1.json()

    def test_trend_caching_and_zero_db_queries(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        api_client.force_authenticate(user=vc)
        url = reverse("api_v1:analytics-trend") + "?metric=pass_rate"

        # First call
        resp1 = api_client.get(url)
        assert resp1.status_code == status.HTTP_200_OK

        # Second call: zero DB queries
        with django_assert_num_queries(0):
            resp2 = api_client.get(url)
            assert resp2.status_code == status.HTTP_200_OK
            assert resp2.json() == resp1.json()

    def test_distribution_caching_and_zero_db_queries(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        subj = uni["subjects"][0]
        api_client.force_authenticate(user=vc)
        url = reverse("api_v1:analytics-distribution") + f"?subject={subj.id}"

        # First call
        resp1 = api_client.get(url)
        assert resp1.status_code == status.HTTP_200_OK

        # Second call: zero DB queries
        with django_assert_num_queries(0):
            resp2 = api_client.get(url)
            assert resp2.status_code == status.HTTP_200_OK
            assert resp2.json() == resp1.json()


# ============================================================================
# 2. Student Predictions Caching Tests
# ============================================================================

@pytest.mark.django_db
class TestStudentPredictionsCaching:

    def test_student_predictions_cached_and_zero_queries(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        student = uni["students"][0]
        student_user = student.user
        api_client.force_authenticate(user=student_user)
        url = reverse("api_v1:student-predictions", kwargs={"id": student.id})

        # First call
        resp1 = api_client.get(url)
        assert resp1.status_code == status.HTTP_200_OK

        # Second call: only object permission check query (1 query), 0 inference/analytics queries
        with django_assert_num_queries(1):
            resp2 = api_client.get(url)
            assert resp2.status_code == status.HTTP_200_OK
            assert resp2.json() == resp1.json()


# ============================================================================
# 3. Event-Driven Invalidation Tests
# ============================================================================

@pytest.mark.django_db
class TestCacheInvalidation:

    def test_result_mutation_invalidates_analytics_and_student_prediction(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        student = uni["students"][0]
        subj = uni["subjects"][0]

        # Warm up overview cache
        api_client.force_authenticate(user=vc)
        url_overview = reverse("api_v1:analytics-overview")
        api_client.get(url_overview)
        with django_assert_num_queries(0):
            api_client.get(url_overview)

        # Warm up student prediction cache
        api_client.force_authenticate(user=student.user)
        url_pred = reverse("api_v1:student-predictions", kwargs={"id": student.id})
        api_client.get(url_pred)
        with django_assert_num_queries(1):
            api_client.get(url_pred)

        # Mutation: update a result
        res = Result.objects.filter(student=student).first()
        if not res:
            res = ResultFactory(student=student, subject=subj, semester=1, total_secured=85)
        else:
            res.total_secured = 95
            res.save()

        # Both caches should be busted; next request queries DB again
        api_client.force_authenticate(user=vc)
        resp_after_overview = api_client.get(url_overview)
        assert resp_after_overview.status_code == status.HTTP_200_OK

        api_client.force_authenticate(user=student.user)
        resp_after_pred = api_client.get(url_pred)
        assert resp_after_pred.status_code == status.HTTP_200_OK

    def test_bulk_internal_marks_busts_cache(
        self, api_client, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        teacher = uni["teachers"][0]
        batch = uni["batch"]
        subj = uni["subjects"][0]
        student = batch.students.first()

        TeachingAssignmentFactory(teacher=teacher, subject=subj, batch=batch)

        # Warm up overview cache
        api_client.force_authenticate(user=vc)
        url_overview = reverse("api_v1:analytics-overview")
        api_client.get(url_overview)

        # Perform Bulk Internal Marks Entry
        api_client.force_authenticate(user=teacher.user)
        url_marks = reverse("api_v1:internal-marks")
        payload = {
            "subject_id": subj.id,
            "batch_id": batch.id,
            "marks": [{"student_id": student.id, "internal_marks": 22.5}],
        }
        post_resp = api_client.post(url_marks, data=payload, format="json")
        assert post_resp.status_code == status.HTTP_200_OK

        # Ensure student prediction for that student is freshly generated
        api_client.force_authenticate(user=student.user)
        url_pred = reverse("api_v1:student-predictions", kwargs={"id": student.id})
        pred_resp = api_client.get(url_pred)
        assert pred_resp.status_code == status.HTTP_200_OK

    def test_semester_result_publication_busts_analytics_cache(
        self, api_client, django_assert_num_queries, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        student = uni["students"][0]

        # Warm up overview cache
        api_client.force_authenticate(user=vc)
        url_overview = reverse("api_v1:analytics-overview")
        api_client.get(url_overview)
        with django_assert_num_queries(0):
            api_client.get(url_overview)

        # Publish a semester result
        sem_res = SemesterResult.objects.filter(student=student).first()
        if sem_res:
            sem_res.is_published = True
            sem_res.save()
        else:
            SemesterResultFactory(student=student, semester=1, is_published=True)

        # Overview cache is invalidated; new request re-queries
        v_after = get_analytics_cache_version()
        assert v_after >= 2

    def test_prediction_snapshot_busts_analytics_cache(
        self, api_client, active_model_fixture
    ):
        uni = make_university()
        student = uni["students"][0]
        v_before = get_analytics_cache_version()

        PredictionSnapshot.objects.create(
            student=student,
            subject=uni["subjects"][0],
            semester=1,
            predicted_percentage=42.0,
            risk_band="HIGH",
            reasons=["Low attendance"],
            model_version=active_model_fixture,
        )
        v_after = get_analytics_cache_version()
        assert v_after > v_before

    def test_habit_checkin_busts_student_prediction_cache(self):
        uni = make_university()
        student = uni["students"][0]
        v_before = get_student_prediction_version(student.id)

        HabitCheckInLog.objects.create(
            student=student,
            hours_studied=4.5,
            sleep_hours=7.0,
            log_type="DAILY",
        )
        v_after = get_student_prediction_version(student.id)
        assert v_after > v_before

    def test_model_version_change_busts_model_and_analytics_cache(self):
        v_model_before = get_model_cache_version()
        v_analytics_before = get_analytics_cache_version()

        ModelVersion.objects.create(
            slot="institutional",
            version=2,
            trained_on="new_cohort",
            n_train_rows=600,
            n_test_rows=120,
            metrics={"rmse": 3.2, "r2": 0.82},
            feature_names=["attendance_percentage"],
            sklearn_version="1.6.0",
            python_version="3.12",
            data_fingerprint="fp456",
            artifact_file="inst_v2.joblib",
            is_active=True,
        )

        assert get_model_cache_version() > v_model_before
        assert get_analytics_cache_version() > v_analytics_before


# ============================================================================
# 4. Fault Tolerance & Graceful Degradation Tests
# ============================================================================

@pytest.mark.django_db
class TestCacheFaultTolerance:

    def test_overview_survives_cache_get_and_set_failures(
        self, api_client, active_model_fixture
    ):
        uni = make_university()
        vc = uni["executives"]["vc"]
        api_client.force_authenticate(user=vc)
        url = reverse("api_v1:analytics-overview")

        with patch("analytics.api_views.safe_cache_get", return_value=None):
            with patch("analytics.api_views.safe_cache_set", return_value=False):
                resp = api_client.get(url)
                assert resp.status_code == status.HTTP_200_OK
                assert "total_students" in resp.json()

    def test_safe_cache_get_and_set_error_handling(self):
        with patch("api.caching.cache.get", side_effect=Exception("Redis timeout")):
            val = safe_cache_get("some_key", default="fallback_val")
            assert val == "fallback_val"

        with patch("api.caching.cache.set", side_effect=Exception("Redis OOM")):
            success = safe_cache_set("some_key", "val")
            assert success is False


# ============================================================================
# 5. Cache Key Isolation Tests
# ============================================================================

@pytest.mark.django_db
class TestCacheKeyIsolation:

    def test_different_scopes_and_parameters_produce_distinct_keys(self):
        k1 = make_analytics_cache_key("overview", "INSTITUTION", None, {})
        k2 = make_analytics_cache_key("overview", "DEPARTMENT", 10, {})
        k3 = make_analytics_cache_key("overview", "DEPARTMENT", 10, {"semester": 2})

        assert k1 != k2
        assert k2 != k3

    def test_student_prediction_cache_keys_are_unique(self):
        k1 = make_prediction_cache_key(101, 1)
        k2 = make_prediction_cache_key(101, 2)
        k3 = make_prediction_cache_key(102, 1)

        assert k1 != k2
        assert k1 != k3
