"""
Unit and integration test suite for Celery Background Workers & Beat Scheduler.

Verifies:
- Celery configuration contracts (broker URL, result backend disabled, late acks, time limits).
- Celery beat schedule static registry.
- Batch prediction snapshot background task (predictions.take_snapshots):
    * Idempotency (skips pre-existing snapshots on rerun)
    * Graceful handling when no active model version exists
    * Zero student PII quarantine in task parameters and logs
- Periodic analytics cache warming background task (analytics.warm_cache):
    * Multi-tier scoped warming (University, School, Department)
    * Cache population verification
    * Fault tolerance (individual scope failure isolation)
"""

from unittest.mock import patch
import joblib
import pytest
import sklearn
from sklearn.linear_model import Ridge
from django.conf import settings
from django.core.cache import cache

from academics.models import Department, School
from analytics.selectors import ScopeContext
from analytics.tasks import warm_analytics_cache
from api.caching import (
    get_analytics_cache_version,
    make_analytics_cache_key,
    safe_cache_get,
)
from config.celery import app as celery_app
from predictions.models import ModelVersion, PredictionSnapshot
from predictions.services import PredictorService
from predictions.tasks import take_prediction_snapshots
from tests.factories import (
    DepartmentFactory,
    ResultFactory,
    SchoolFactory,
    SemesterResultFactory,
    StudentProfileFactory,
    SubjectFactory,
    make_university,
)


@pytest.fixture
def active_model(tmp_path, monkeypatch):
    """Creates, registers, and activates a minimal Ridge pipeline."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(artifact_dir))

    import pandas as pd

    feature_names = ["attendance_percentage", "hours_studied"]
    X = pd.DataFrame([[40.0, 5.0], [90.0, 25.0]], columns=feature_names)
    y = [35.0, 85.0]
    model = Ridge()
    model.fit(X, y)

    artifact_name = "test_celery_model.joblib"
    joblib.dump(model, artifact_dir / artifact_name)

    PredictorService.clear_cache()

    mv = ModelVersion.objects.create(
        slot="baseline",
        version=1,
        trained_on="test_celery_data",
        n_train_rows=2,
        n_test_rows=1,
        metrics={"rmse": 0.5},
        feature_names=feature_names,
        sklearn_version=sklearn.__version__,
        python_version="3.12",
        data_fingerprint="sha256celerytest",
        artifact_file=artifact_name,
        is_active=True,
    )
    return mv


# ============================================================================
# 1. Configuration Contract Tests
# ============================================================================


@pytest.mark.django_db
class TestCeleryConfigurationContracts:
    def test_celery_settings_contracts(self):
        """Verify Celery broker, result backend, prefetch, and time limits adhere to standards."""
        assert settings.CELERY_BROKER_URL is not None
        assert settings.CELERY_RESULT_BACKEND is None
        assert settings.CELERY_TASK_IGNORE_RESULT is True
        assert settings.CELERY_TASK_ACKS_LATE is True
        assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1
        assert settings.CELERY_TASK_SOFT_TIME_LIMIT == 300
        assert settings.CELERY_TASK_TIME_LIMIT == 330

    def test_celery_beat_schedule_contracts(self):
        """Verify Celery Beat schedule contains expected periodic task registrations."""
        schedule = settings.CELERY_BEAT_SCHEDULE

        assert "take-prediction-snapshots-weekly" in schedule
        snap_entry = schedule["take-prediction-snapshots-weekly"]
        assert snap_entry["task"] == "predictions.take_snapshots"
        assert snap_entry["schedule"] == 604800.0
        assert snap_entry.get("kwargs", {}).get("checkpoint") == "weekly"

        assert "warm-analytics-cache-periodic" in schedule
        warm_entry = schedule["warm-analytics-cache-periodic"]
        assert warm_entry["task"] == "analytics.warm_cache"
        assert warm_entry["schedule"] == 1800.0

    def test_celery_app_tasks_registered(self):
        """Verify all shared tasks are registered in the Celery app registry."""
        task_names = celery_app.tasks.keys()
        assert "predictions.take_snapshots" in task_names
        assert "analytics.warm_cache" in task_names


# ============================================================================
# 2. Prediction Snapshots Task Tests
# ============================================================================


@pytest.mark.django_db
class TestPredictionSnapshotsTask:
    def test_take_snapshots_no_active_model_skips_gracefully(self):
        """When no active ModelVersion exists, task returns skipped status without error."""
        PredictorService.clear_cache()
        ModelVersion.objects.all().delete()

        result = take_prediction_snapshots.delay(checkpoint="test_cp")
        data = result.get() if hasattr(result, "get") else result

        assert data["status"] == "skipped"
        assert "No active ModelVersion" in data["reason"]
        assert data["created_count"] == 0

    def test_take_snapshots_execution_and_idempotency(self, active_model):
        """Verify snapshot creation for active students and idempotency on duplicate invocation."""
        uni = make_university()
        student1 = StudentProfileFactory(course=uni["course"])
        student2 = StudentProfileFactory(course=uni["course"])

        # Initial run: creates snapshots
        res1 = take_prediction_snapshots.delay(checkpoint="week_01", slot="baseline")
        data1 = res1.get() if hasattr(res1, "get") else res1

        assert data1["status"] == "success"
        assert data1["created_count"] > 0
        assert data1["skipped_count"] == 0

        initial_count = PredictionSnapshot.objects.filter(checkpoint="week_01").count()
        assert initial_count >= 2

        # Second run with same checkpoint: skips already computed snapshots (idempotent)
        res2 = take_prediction_snapshots.delay(checkpoint="week_01", slot="baseline")
        data2 = res2.get() if hasattr(res2, "get") else res2

        assert data2["status"] == "success"
        assert data2["created_count"] == 0
        assert data2["skipped_count"] >= initial_count
        assert PredictionSnapshot.objects.filter(checkpoint="week_01").count() == initial_count

    def test_take_snapshots_zero_pii_in_return_payload(self, active_model):
        """Verify task results contain aggregate counts and checkpoint names only (zero PII)."""
        uni = make_university()
        student = StudentProfileFactory(course=uni["course"])

        res = take_prediction_snapshots.delay(checkpoint="pii_check", slot="baseline")
        data = res.get() if hasattr(res, "get") else res

        # Ensure no student names, emails, roll numbers, or personal attributes are returned
        for key in ["name", "email", "roll_no", "username", "first_name", "last_name"]:
            assert key not in data


# ============================================================================
# 3. Analytics Cache Warming Task Tests
# ============================================================================


@pytest.mark.django_db
class TestAnalyticsCacheWarmingTask:
    def test_warm_analytics_cache_populates_scopes(self):
        """Verify warm_analytics_cache warms institutional, school, and department caches."""
        cache.clear()
        uni = make_university()
        school = uni["school"]
        dept = uni["department"]

        res = warm_analytics_cache.delay()
        data = res.get() if hasattr(res, "get") else res

        assert data["status"] == "success"
        assert data["warmed_scopes"] >= 3  # University + School + Dept
        assert data["errors"] == 0

        version = get_analytics_cache_version()

        # 1. Check University scope cache
        uni_scope = ScopeContext(
            user=None,
            role="ADMIN",
            scope_level="university",
            is_university_wide=True,
            allowed_school_ids=set(),
            allowed_department_ids=set(),
            allowed_course_ids=set(),
            allowed_batch_ids=set(),
            allowed_subject_ids=set(),
        )
        uni_key = make_analytics_cache_key("overview", uni_scope, {})
        uni_cached = safe_cache_get(uni_key, version=version)
        assert uni_cached is not None
        assert "total_students" in uni_cached

        # 2. Check School scope cache
        school_scope = ScopeContext(
            user=None,
            role="DEAN",
            scope_level="school",
            is_university_wide=False,
            allowed_school_ids={school.id},
            allowed_department_ids={dept.id},
            allowed_course_ids={uni["course"].id},
            allowed_batch_ids={uni["batch"].id},
            allowed_subject_ids=set(),
        )
        school_key = make_analytics_cache_key("overview", school_scope, {})
        school_cached = safe_cache_get(school_key, version=version)
        assert school_cached is not None
        assert "total_students" in school_cached

        # 3. Check Department scope cache
        dept_scope = ScopeContext(
            user=None,
            role="HOD",
            scope_level="department",
            is_university_wide=False,
            allowed_school_ids={school.id},
            allowed_department_ids={dept.id},
            allowed_course_ids={uni["course"].id},
            allowed_batch_ids={uni["batch"].id},
            allowed_subject_ids=set(),
        )
        dept_key = make_analytics_cache_key("overview", dept_scope, {})
        dept_cached = safe_cache_get(dept_key, version=version)
        assert dept_cached is not None
        assert "total_students" in dept_cached

    def test_warm_analytics_cache_fault_tolerance(self):
        """Verify an error in one scope does not abort warming for remaining scopes."""
        cache.clear()
        uni = make_university()

        valid_payload = {
            "total_students": 10,
            "pass_rate": 90.0,
            "average_percentage": 75.0,
            "at_risk_count": 0,
            "at_risk_rate": 0.0,
            "published_share": 100.0,
            "model": None,
        }

        # Simulate failure during school scope aggregation
        with patch("analytics.tasks.get_analytics_overview") as mock_overview:
            # First call (university) succeeds, second call (school) raises, third (dept) succeeds
            mock_overview.side_effect = [
                valid_payload,
                Exception("Database timeout on school aggregation"),
                valid_payload,
            ]

            res = warm_analytics_cache.delay()
            data = res.get() if hasattr(res, "get") else res

            assert data["status"] == "partial_success"
            assert data["warmed_scopes"] == 2
            assert data["errors"] == 1
