import os
import joblib
import pytest
import sklearn
from io import StringIO
from pathlib import Path
from sklearn.linear_model import Ridge
from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError


@pytest.mark.django_db
class TestPredictionsService:
    """Tests ModelVersion registry, path safety, and PredictorService."""

    @pytest.fixture
    def dummy_pipeline(self, tmp_path, monkeypatch):
        """Creates and saves a minimal compliant Ridge pipeline in a tmp artifact directory."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(artifact_dir))

        import pandas as pd

        # Train a tiny Ridge regressor with explicit feature names
        feature_names = ["attendance_percentage", "hours_studied"]
        X = pd.DataFrame([[50.0, 10.0], [90.0, 25.0]], columns=feature_names)
        y = [45.0, 85.0]
        model = Ridge()
        model.fit(X, y)

        artifact_name = "test_ridge_v1.joblib"
        joblib.dump(model, artifact_dir / artifact_name)

        return {
            "artifact_dir": artifact_dir,
            "artifact_name": artifact_name,
            "feature_names": ["attendance_percentage", "hours_studied"],
            "sklearn_version": sklearn.__version__,
        }

    def test_resolve_artifact_path_rejects_escape(self):
        """resolve_artifact_path must strictly reject path traversal and directory separators."""
        from predictions.services import resolve_artifact_path

        for escape in ["../secret.joblib", "sub/model.joblib", "evil\\file.joblib", "/etc/passwd"]:
            with pytest.raises(ValueError, match="Path escape attempt"):
                resolve_artifact_path(escape)

        with pytest.raises(ValueError):
            resolve_artifact_path("")

    def test_model_version_active_uniqueness_constraint(self):
        """Database constraint must prevent more than one active model per slot."""
        from predictions.models import ModelVersion

        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="synthetic_sample",
            n_train_rows=100,
            n_test_rows=20,
            metrics={"rmse": 4.5},
            feature_names=["attendance_percentage"],
            sklearn_version=sklearn.__version__,
            python_version="3.12",
            data_fingerprint="abc123sha",
            artifact_file="model_v1.joblib",
            is_active=True,
        )

        # Second active model in the same slot must fail unique constraint
        with pytest.raises(IntegrityError):
            ModelVersion.objects.create(
                slot="baseline",
                version=2,
                trained_on="synthetic_sample_v2",
                n_train_rows=150,
                n_test_rows=30,
                metrics={"rmse": 4.1},
                feature_names=["attendance_percentage"],
                sklearn_version=sklearn.__version__,
                python_version="3.12",
                data_fingerprint="def456sha",
                artifact_file="model_v2.joblib",
                is_active=True,
            )

    def test_predictor_service_loads_active_model_and_predicts(self, dummy_pipeline):
        """PredictorService successfully loads active model and generates bounded predictions."""
        from predictions.models import ModelVersion
        from predictions.services import PredictorService

        PredictorService.clear_cache()

        mv = ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="test_data",
            n_train_rows=2,
            n_test_rows=1,
            metrics={"rmse": 1.2},
            feature_names=dummy_pipeline["feature_names"],
            sklearn_version=dummy_pipeline["sklearn_version"],
            python_version="3.12",
            data_fingerprint="sha256dummy",
            artifact_file=dummy_pipeline["artifact_name"],
            is_active=True,
        )

        results = PredictorService.predict(
            "baseline",
            [
                {"attendance_percentage": 85.0, "hours_studied": 20.0},
                {"attendance_percentage": 30.0, "hours_studied": 2.0},
            ],
        )

        assert len(results) == 2
        assert results[0]["status"] == "success"
        assert 0.0 <= results[0]["predicted_percentage"] <= 100.0
        assert results[1]["status"] == "success"
        assert results[1]["is_at_risk"] is True

    def test_predictor_service_refuses_mismatched_sklearn_version(self, dummy_pipeline):
        """PredictorService refuses to load an artifact trained with an incompatible sklearn version."""
        from predictions.models import ModelVersion
        from predictions.services import PredictorService, IncompatibleEnvironmentError

        PredictorService.clear_cache()

        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="legacy_run",
            n_train_rows=10,
            n_test_rows=2,
            metrics={},
            feature_names=dummy_pipeline["feature_names"],
            sklearn_version="0.22.1",  # incompatible version
            python_version="3.8",
            data_fingerprint="fingerprint",
            artifact_file=dummy_pipeline["artifact_name"],
            is_active=True,
        )

        with pytest.raises(IncompatibleEnvironmentError, match="incompatible model"):
            PredictorService.load("baseline")

    def test_predictor_service_insufficient_data_when_missing_features(self, dummy_pipeline):
        """PredictorService returns 'insufficient_data' instead of fabricating default numbers."""
        from predictions.models import ModelVersion
        from predictions.services import PredictorService

        PredictorService.clear_cache()

        ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="test",
            n_train_rows=2,
            n_test_rows=1,
            metrics={},
            feature_names=dummy_pipeline["feature_names"],
            sklearn_version=dummy_pipeline["sklearn_version"],
            python_version="3.12",
            data_fingerprint="sha",
            artifact_file=dummy_pipeline["artifact_name"],
            is_active=True,
        )

        # Missing 'hours_studied'
        results = PredictorService.predict(
            "baseline",
            [
                {"attendance_percentage": 80.0},
                {"attendance_percentage": 75.0, "hours_studied": None},
            ],
        )

        assert len(results) == 2
        assert results[0]["status"] == "insufficient_data"
        assert any("hours_studied" in p for p in results[0]["problems"])
        assert results[1]["status"] == "insufficient_data"

    def test_models_list_command(self):
        """models_list management command outputs table cleanly."""
        out = StringIO()
        call_command("models_list", stdout=out)
        output = out.getvalue()
        assert "Slot" in output or "No registered model versions" in output

    def test_models_activate_command(self, dummy_pipeline):
        """models_activate atomically activates the specified version and deactivates others."""
        from predictions.models import ModelVersion

        v1 = ModelVersion.objects.create(
            slot="baseline",
            version=1,
            trained_on="run1",
            n_train_rows=10,
            n_test_rows=2,
            metrics={},
            feature_names=dummy_pipeline["feature_names"],
            sklearn_version=dummy_pipeline["sklearn_version"],
            python_version="3.12",
            data_fingerprint="sha1",
            artifact_file=dummy_pipeline["artifact_name"],
            is_active=True,
        )

        v2 = ModelVersion.objects.create(
            slot="baseline",
            version=2,
            trained_on="run2",
            n_train_rows=20,
            n_test_rows=5,
            metrics={},
            feature_names=dummy_pipeline["feature_names"],
            sklearn_version=dummy_pipeline["sklearn_version"],
            python_version="3.12",
            data_fingerprint="sha2",
            artifact_file=dummy_pipeline["artifact_name"],
            is_active=False,
        )

        out = StringIO()
        call_command("models_activate", v2.id, stdout=out)

        v1.refresh_from_db()
        v2.refresh_from_db()

        assert v1.is_active is False
        assert v2.is_active is True
        assert "Successfully activated" in out.getvalue()
