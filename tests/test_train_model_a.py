import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from django.conf import settings
from django.core.management import call_command
from predictions.models import ModelVersion


@pytest.fixture
def synthetic_kaggle_csv(tmp_path):
    """Creates a small mock Kaggle CSV matching StudentPerformanceFactors schema."""
    np.random.seed(42)
    n = 100

    hours = np.random.uniform(5, 35, n)
    attendance = np.random.uniform(50, 100, n)
    sleep = np.random.uniform(5, 10, n)
    prev = np.random.uniform(40, 95, n)
    tutor = np.random.randint(0, 5, n)
    phys = np.random.uniform(1, 10, n)

    # Score correlated with attendance and hours studied
    score = np.clip(0.4 * attendance + 0.8 * hours + 0.2 * prev + np.random.normal(0, 3, n), 10, 98)

    df = pd.DataFrame({
        "Hours_Studied": hours,
        "Attendance": attendance,
        "Sleep_Hours": sleep,
        "Previous_Scores": prev,
        "Tutoring_Sessions": tutor,
        "Physical_Activity": phys,
        "Exam_Score": score,
        # Protected demographic columns (must be excluded)
        "Gender": ["Male", "Female"] * (n // 2),
        "Learning_Disabilities": [0, 1] * (n // 2),
        # Unapproved socio-economic proxies (must be excluded)
        "Family_Income": ["Low", "Medium", "High", "Medium"] * (n // 4),
        "Distance_from_Home": ["Near", "Far"] * (n // 2),
    })

    # Add 2 out-of-bounds score rows that should be dropped
    oob_rows = pd.DataFrame([
        {
            "Hours_Studied": 10, "Attendance": 80, "Sleep_Hours": 7, "Previous_Scores": 60,
            "Tutoring_Sessions": 1, "Physical_Activity": 2, "Exam_Score": 150.0,
            "Gender": "Male", "Learning_Disabilities": 0, "Family_Income": "High", "Distance_from_Home": "Near"
        },
        {
            "Hours_Studied": 10, "Attendance": 80, "Sleep_Hours": 7, "Previous_Scores": 60,
            "Tutoring_Sessions": 1, "Physical_Activity": 2, "Exam_Score": -10.0,
            "Gender": "Female", "Learning_Disabilities": 0, "Family_Income": "Low", "Distance_from_Home": "Far"
        }
    ])
    df = pd.concat([df, oob_rows], ignore_index=True)

    csv_path = tmp_path / "StudentPerformanceFactors.csv"
    df.to_csv(csv_path, index=False)
    return tmp_path, csv_path


@pytest.mark.django_db
class TestTrainModelA:
    """Tests Model A baseline training pipeline, evaluation metrics, and registration."""

    def test_load_kaggle_spf_cleans_and_renames(self, synthetic_kaggle_csv):
        from edupulse_ml.datasets.kaggle_spf import load_kaggle_spf

        tmp_dir, csv_path = synthetic_kaggle_csv
        X, y, meta = load_kaggle_spf(csv_path)

        # Out-of-bounds rows must be dropped (102 total -> 100 valid)
        assert len(X) == 100
        assert len(y) == 100
        assert meta["dropped_oob_scores"] == 2

        # Verify only approved baseline features exist
        expected_features = {
            "hours_studied", "attendance_percentage", "sleep_hours",
            "previous_score", "tutoring_sessions", "physical_activity"
        }
        assert set(X.columns) == expected_features

        # Verify protected attributes are completely absent
        assert "Gender" not in X.columns
        assert "gender" not in X.columns
        assert "Learning_Disabilities" not in X.columns
        assert "learning_disabilities" not in X.columns
        assert "Family_Income" not in X.columns
        assert "family_income" not in X.columns

        # Verify sha256 fingerprint generated
        assert len(meta["data_fingerprint"]) == 64

    def test_evaluate_regression_metrics(self):
        from edupulse_ml.evaluate import evaluate_regression

        y_true = np.array([30.0, 45.0, 50.0, 80.0])
        y_pred = np.array([35.0, 40.0, 52.0, 75.0])

        metrics = evaluate_regression(y_true, y_pred, pass_mark=40.0)

        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2" in metrics
        assert "confusion_matrix" in metrics
        cm = metrics["confusion_matrix"]
        assert "true_pass" in cm
        assert "true_fail" in cm
        assert "false_pass" in cm
        assert "false_fail" in cm

    def test_train_model_a_command_execution(self, synthetic_kaggle_csv, tmp_path, monkeypatch):
        tmp_dir, _ = synthetic_kaggle_csv
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(artifact_dir))

        # Run training command
        call_command("train_model_a", data_dir=str(tmp_dir))

        # 1. Verify ModelVersion created in database
        mv = ModelVersion.objects.filter(slot="baseline").first()
        assert mv is not None
        assert mv.slot == "baseline"
        assert mv.version == 1
        assert mv.is_active is False  # Safe deployment: not auto-activated
        assert "Kaggle" in mv.trained_on
        assert mv.n_train_rows + mv.n_test_rows == 100
        assert len(mv.data_fingerprint) == 64

        # 2. Verify chosen model beats dummy baseline
        metrics = mv.metrics
        assert "chosen_model" in metrics
        assert "test_metrics" in metrics
        assert "dummy_metrics" in metrics
        assert metrics["test_metrics"]["rmse"] < metrics["dummy_metrics"]["rmse"]

        # 3. Verify artifact file exists in MODEL_ARTIFACT_DIR
        artifact_path = artifact_dir / mv.artifact_file
        assert artifact_path.is_file()

        # 4. Verify metrics.json exists alongside artifact
        metrics_file = artifact_dir / "metrics.json"
        assert metrics_file.is_file()
        with open(metrics_file, "r", encoding="utf-8") as f:
            saved_metrics = json.load(f)
        assert saved_metrics["slot"] == "baseline"

        # 5. Verify MODEL_CARD_A.md generated with required disclosures
        doc_path = Path(settings.BASE_DIR).parent / "docs" / "MODEL_CARD_A.md"
        assert doc_path.is_file()
        content = doc_path.read_text(encoding="utf-8")
        assert "The dataset is widely regarded as synthetic; metrics show the pipeline works, not real-world accuracy" in content
        assert "verify the license on the dataset page" in content
        assert "Dropped Attributes & Ethical Governance" in content
