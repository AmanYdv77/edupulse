"""
Tests for Model Router, Explainability, and Honest Provenance Labels (Task A19).
Verifies:
1. PredictorService.active_for() prioritizes institute model over baseline model.
2. Falls back to baseline model if institute features are missing or institute model is inactive.
3. Returns None if features for neither model are satisfied.
4. Honest provenance labels match required specifications.
5. Plain-language factor explanations with linear attribution, non-linear fallback, and protected attribute exclusion.
6. Advisory disclaimer and ethical terminology ('Estimated Risk', never 'AI Grade') in views and templates.
"""

import os
import joblib
import pytest
import sklearn
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pandas as pd
from django.conf import settings
from django.test import Client
from django.urls import reverse

from predictions.models import ModelVersion
from predictions.services import (
    DEFAULT_DISCLAIMER,
    PredictorService,
    PredictionResult,
    get_model_label,
    predict_for_students,
    predict_current_subjects,
)
from predictions.explain import (
    explain_prediction,
    FEATURE_HUMAN_NAMES,
)
from tests.factories import (
    StudentProfileFactory,
    SubjectFactory,
    SemesterResultFactory,
    ResultFactory,
    TeacherProfileFactory,
    TeachingAssignmentFactory,
)


@pytest.fixture
def model_artifacts_dir(tmp_path, monkeypatch):
    """Sets up a temporary artifact directory for test models."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(artifact_dir))
    return artifact_dir


@pytest.fixture
def trained_models(model_artifacts_dir):
    """Creates minimal baseline and institute model pipelines."""
    # 1. Baseline Model (features: attendance_percentage, hours_studied, previous_score)
    baseline_features = ["attendance_percentage", "hours_studied", "previous_score"]
    X_base = pd.DataFrame([
        [60.0, 10.0, 50.0],
        [85.0, 20.0, 75.0],
        [95.0, 30.0, 90.0],
    ], columns=baseline_features)
    y_base = [50.0, 75.0, 90.0]

    baseline_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", Ridge()),
    ])
    baseline_pipe.fit(X_base, y_base)
    baseline_file = "baseline_v1.joblib"
    joblib.dump(baseline_pipe, model_artifacts_dir / baseline_file)

    # 2. Institute Model (features: attendance_percentage, previous_score, internal_assessment_score)
    inst_features = ["attendance_percentage", "previous_score", "internal_assessment_score"]
    X_inst = pd.DataFrame([
        [60.0, 50.0, 15.0],
        [80.0, 70.0, 22.0],
        [95.0, 90.0, 28.0],
    ], columns=inst_features)
    y_inst = [55.0, 72.0, 92.0]

    inst_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", Ridge()),
    ])
    inst_pipe.fit(X_inst, y_inst)
    inst_file = "institute_v1.joblib"
    joblib.dump(inst_pipe, model_artifacts_dir / inst_file)

    PredictorService.clear_cache()

    return {
        "baseline_file": baseline_file,
        "baseline_features": baseline_features,
        "institute_file": inst_file,
        "institute_features": inst_features,
        "baseline_pipe": baseline_pipe,
        "inst_pipe": inst_pipe,
    }


# ============================================================================
# EXPLAINABILITY TESTS
# ============================================================================

class TestExplainability:
    """Tests for app/predictions/explain.py."""

    def test_linear_model_explanation(self, trained_models):
        """Pipeline with StandardScaler and Ridge produces directional top factors."""
        model = trained_models["baseline_pipe"]
        feature_names = trained_models["baseline_features"]
        feature_values = {
            "attendance_percentage": 95.0,
            "hours_studied": 30.0,
            "previous_score": 90.0,
        }

        factors = explain_prediction(model, feature_names, feature_values)
        assert len(factors) <= 3
        assert len(factors) > 0

        for f in factors:
            assert "feature" in f
            assert "name" in f
            assert "impact" in f
            assert "direction" in f
            assert f["direction"] in ("positive", "negative", "neutral")
            assert f["name"] in FEATURE_HUMAN_NAMES.values()
            assert "%" in f["impact"]

    def test_protected_attributes_strictly_excluded(self, trained_models):
        """Protected demographic attributes must NEVER be returned in explanatory factors."""
        model = trained_models["baseline_pipe"]
        # Add protected attributes to feature names and values
        feature_names = ["attendance_percentage", "hours_studied", "gender", "category"]
        feature_values = {
            "attendance_percentage": 90.0,
            "hours_studied": 25.0,
            "gender": "Female",
            "category": "General",
        }

        factors = explain_prediction(model, feature_names, feature_values)
        factor_features = [f["feature"] for f in factors]
        assert "gender" not in factor_features
        assert "category" not in factor_features

    def test_missing_features_returns_insufficient_data_factor(self, trained_models):
        """Missing required features return an informative 'Insufficient Data' factor."""
        model = trained_models["baseline_pipe"]
        feature_names = ["attendance_percentage", "hours_studied"]
        feature_values = {
            "attendance_percentage": 85.0,
            "hours_studied": None,  # Missing
        }

        factors = explain_prediction(model, feature_names, feature_values)
        assert len(factors) == 1
        assert factors[0]["feature"] == "missing_data"
        assert "hours_studied" in factors[0]["description"]

    def test_non_linear_model_fallback(self):
        """Models without linear coefficients return global importance note."""
        class DummyNonLinearModel:
            pass

        model = DummyNonLinearModel()
        feature_names = ["attendance_percentage", "hours_studied"]
        feature_values = {
            "attendance_percentage": 80.0,
            "hours_studied": 20.0,
        }

        factors = explain_prediction(model, feature_names, feature_values)
        assert len(factors) > 0
        for f in factors:
            assert "per-student attribution is unavailable" in f["description"]


# ============================================================================
# MODEL LABEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestModelLabels:
    """Tests honest provenance labels generated for predictions."""

    def test_get_model_label_none(self):
        assert get_model_label(None) == "No calibrated model available"

    def test_get_model_label_baseline(self):
        mv = ModelVersion(slot="baseline", version=1)
        assert get_model_label(mv) == "Baseline estimate (public sample data)"

    def test_get_model_label_institute(self):
        mv = ModelVersion(slot="institute", version=2, n_train_rows=1250)
        assert get_model_label(mv) == "Institute-calibrated estimate (model v2, trained on 1250 records)"


# ============================================================================
# MODEL ROUTER TESTS
# ============================================================================

@pytest.mark.django_db
class TestModelRouter:
    """Tests PredictorService.active_for() routing logic and precedence."""

    def test_active_for_selects_institute_when_features_available(self, trained_models):
        """When institute model is active and student has all required features, institute is selected."""
        PredictorService.clear_cache()

        # Create active baseline
        mv_base = ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=500,
            n_test_rows=100,
            metrics={"rmse": 4.2},
            feature_names=trained_models["baseline_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="base_hash",
            artifact_file=trained_models["baseline_file"],
            is_active=True,
        )

        # Create active institute
        mv_inst = ModelVersion.objects.create(
            slot="institute",
            version=1,
            trained_on="institute_records",
            n_train_rows=1200,
            n_test_rows=240,
            metrics={"rmse": 3.1},
            feature_names=trained_models["institute_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="inst_hash",
            artifact_file=trained_models["institute_file"],
            is_active=True,
        )

        # Create student with attendance, previous score, and internal marks
        student = StudentProfileFactory()
        SemesterResultFactory(
            student=student,
            semester=1,
            attendance_percentage=85.0,
            percentage=78.0,
            hours_studied_per_week=20.0,
        )
        subj = SubjectFactory(course=student.course, semester=1, internal_max=30)
        ResultFactory(
            student=student,
            subject=subj,
            internal_marks=24,
        )

        selected_model = PredictorService.active_for(student)
        assert selected_model is not None
        assert selected_model.id == mv_inst.id
        assert selected_model.slot == "institute"

    def test_active_for_falls_back_to_baseline_when_institute_features_missing(self, trained_models):
        """When student lacks institute features (e.g. internal marks), router falls back to baseline."""
        PredictorService.clear_cache()

        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=500,
            n_test_rows=100,
            metrics={"rmse": 4.2},
            feature_names=trained_models["baseline_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="base_hash",
            artifact_file=trained_models["baseline_file"],
            is_active=True,
        )

        ModelVersion.objects.create(
            slot="institute",
            version=1,
            trained_on="institute_records",
            n_train_rows=1200,
            n_test_rows=240,
            metrics={"rmse": 3.1},
            feature_names=trained_models["institute_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="inst_hash",
            artifact_file=trained_models["institute_file"],
            is_active=True,
        )

        # Student has SemesterResult (attendance, hours, prev_score) but NO Result (no internal assessment marks)
        student = StudentProfileFactory()
        SemesterResultFactory(
            student=student,
            semester=1,
            attendance_percentage=88.0,
            percentage=82.0,
            hours_studied_per_week=18.0,
        )

        selected_model = PredictorService.active_for(student)
        assert selected_model is not None
        assert selected_model.slot == "baseline"

    def test_active_for_returns_none_when_all_features_missing(self, trained_models):
        """When student has no academic or habit telemetry, router returns None."""
        PredictorService.clear_cache()

        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=500,
            n_test_rows=100,
            metrics={"rmse": 4.2},
            feature_names=trained_models["baseline_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="base_hash",
            artifact_file=trained_models["baseline_file"],
            is_active=True,
        )

        student = StudentProfileFactory()
        # No SemesterResult, no habit logs, no results

        selected_model = PredictorService.active_for(student)
        assert selected_model is None


# ============================================================================
# PREDICTION INFERENCE & PROVENANCE INTEGRATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestPredictionResultsIntegration:
    """Tests predict_for_students integration with honest provenance, factors, and disclaimers."""

    def test_predict_for_students_includes_metadata_and_factors(self, trained_models):
        PredictorService.clear_cache()

        mv_inst = ModelVersion.objects.create(
            slot="institute",
            version=1,
            trained_on="institute_records",
            n_train_rows=800,
            n_test_rows=160,
            metrics={"rmse": 3.0},
            feature_names=trained_models["institute_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="inst_hash_2",
            artifact_file=trained_models["institute_file"],
            is_active=True,
        )

        student = StudentProfileFactory(current_semester=1)
        subj = SubjectFactory(course=student.course, semester=1, internal_max=30)
        SemesterResultFactory(
            student=student,
            semester=1,
            attendance_percentage=90.0,
            percentage=85.0,
        )
        ResultFactory(
            student=student,
            subject=subj,
            semester=1,
            internal_marks=27,
        )

        results = predict_for_students([student], slot="institute")
        assert len(results) >= 1
        res = results[0]

        assert res.model_slot == "institute"
        assert res.model_version == 1
        assert "Institute-calibrated estimate (model v1, trained on 800 records)" in res.model_label
        assert res.disclaimer == DEFAULT_DISCLAIMER
        assert len(res.factors) > 0
        assert res.predicted_percentage is not None

    def test_insufficient_data_produces_clean_unfabricated_result(self, trained_models):
        PredictorService.clear_cache()

        mv_base = ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=500,
            n_test_rows=100,
            metrics={"rmse": 4.2},
            feature_names=trained_models["baseline_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="base_hash_3",
            artifact_file=trained_models["baseline_file"],
            is_active=True,
        )

        student = StudentProfileFactory(current_semester=1)
        SubjectFactory(course=student.course, semester=1)
        # Student has NO telemetry records

        results = predict_for_students([student], slot="baseline")
        assert len(results) >= 1
        res = results[0]

        assert res.predicted_percentage is None
        assert res.risk_band == "insufficient_data"
        assert res.status == "insufficient_data"
        assert any("Missing required telemetry" in r for r in res.reasons)
        assert len(res.factors) == 1
        assert res.factors[0]["feature"] == "missing_data"


# ============================================================================
# TEMPLATE & ADVISORY NOTICE TESTS
# ============================================================================

@pytest.mark.django_db
class TestViewAdvisoriesAndTerminology:
    """Verifies that templates render advisory notices and avoid forbidden 'AI Grade' terms."""

    def test_my_predictions_view_contains_advisory_notice_and_no_ai_grade(self, client: Client, trained_models):
        student = StudentProfileFactory(current_semester=1)
        client.force_login(student.user)

        # Baseline model active
        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=500,
            n_test_rows=100,
            metrics={"rmse": 4.2},
            feature_names=trained_models["baseline_features"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="base_hash_ui",
            artifact_file=trained_models["baseline_file"],
            is_active=True,
        )

        url = reverse("my_predictions")
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode("utf-8")

        # Must include advisory notice
        assert "Advisory Notice:" in content
        assert "Estimates are indicative forecasts based on historical patterns" in content

        # Must NOT include "AI Grade"
        assert "AI Grade" not in content

        # Must include "Estimated Risk"
        assert "Estimated Risk" in content

    def test_at_risk_students_view_contains_advisory_notice_and_no_ai_grade(self, client: Client):
        teacher = TeacherProfileFactory()
        client.force_login(teacher.user)

        url = reverse("at_risk_students")
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode("utf-8")

        # Must include advisory notice
        assert "Advisory Notice:" in content
        assert "Estimates are indicative forecasts based on historical patterns" in content

        # Must NOT include "AI Grade"
        assert "AI Grade" not in content

        # Must include "Estimated Risk"
        assert "Estimated Risk" in content
