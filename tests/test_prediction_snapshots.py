"""
Unit and integration tests for Task A17:
- PredictionSnapshot immutability guard and persistence
- Unified pass mark and table-driven risk classification
- Single-pass vectorized batch prediction across cohorts
- Idempotent management command take_prediction_snapshots
- Scoped snapshot selectors for institutional hierarchy
"""
import joblib
import pytest
import sklearn
from io import StringIO
from unittest.mock import patch
from sklearn.linear_model import Ridge
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from predictions.models import ModelVersion, PredictionSnapshot
from predictions.grades import risk_band_for, is_at_risk, letter_grade_for
from predictions.services import PredictorService, predict_for_students
from predictions.selectors import scoped_snapshots_for
from tests.factories import make_university


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

    artifact_name = "test_snapshot_model.joblib"
    joblib.dump(model, artifact_dir / artifact_name)

    PredictorService.clear_cache()

    mv = ModelVersion.objects.create(
        slot="baseline",
        version=1,
        trained_on="test_snapshot_data",
        n_train_rows=2,
        n_test_rows=1,
        metrics={"rmse": 0.5},
        feature_names=feature_names,
        sklearn_version=sklearn.__version__,
        python_version="3.12",
        data_fingerprint="sha256snapshot",
        artifact_file=artifact_name,
        is_active=True,
    )
    return mv


@pytest.mark.django_db
class TestGradesAndRisk:
    def test_pass_mark_constant(self):
        assert getattr(settings, "PASS_MARK_PERCENT", None) == 40.0

    def test_risk_band_for(self):
        assert risk_band_for(39.9) == "high"
        assert risk_band_for(40.0) == "medium"
        assert risk_band_for(59.9) == "medium"
        assert risk_band_for(60.0) == "low"
        assert risk_band_for(95.0) == "low"
        assert risk_band_for(None) == "insufficient_data"

    def test_is_at_risk(self):
        assert is_at_risk(35.0) is True
        assert is_at_risk("high") is True
        assert is_at_risk("HIGH") is True
        assert is_at_risk(45.0) is False
        assert is_at_risk("medium") is False
        assert is_at_risk("low") is False
        assert is_at_risk(None) is True
        assert is_at_risk("insufficient_data") is True

    def test_letter_grade_for(self):
        assert letter_grade_for(None) == "F"
        assert letter_grade_for(35.0) == "F"
        assert letter_grade_for(45.0) == "C"
        assert letter_grade_for(95.0) == "O"


@pytest.mark.django_db
class TestPredictionSnapshotModel:
    def test_snapshot_creation_and_immutability(self, active_model):
        from django.core.exceptions import ValidationError

        tree = make_university(students_per_batch=1)
        student = tree["students"][0]
        subject = tree["subjects"][0]

        snapshot = PredictionSnapshot.objects.create(
            student=student,
            subject=subject,
            semester=1,
            taken_at=timezone.now(),
            checkpoint="midterm_2026",
            model_version=active_model,
            features={"attendance_percentage": 75.0, "hours_studied": 10.0},
            predicted_percentage=68.5,
            risk_band="low",
            reasons=[],
        )
        assert snapshot.pk is not None
        assert snapshot.is_at_risk is False

        # Attempting to mutate an existing snapshot must raise ValidationError
        snapshot.predicted_percentage = 42.0
        with pytest.raises(ValidationError, match="immutable and cannot be updated"):
            snapshot.save()


@pytest.mark.django_db
class TestBatchPredictions:
    def test_predict_for_students_single_model_call(self, active_model):
        """predict_for_students must vectorize predictions and call model.predict exactly once."""
        tree = make_university(students_per_batch=4)
        students = tree["students"]

        loaded_model = PredictorService.load("baseline")
        real_predict = loaded_model.predict

        with patch.object(loaded_model, "predict", side_effect=real_predict) as mock_predict:
            results = predict_for_students(students, slot="baseline")
            # 4 students * 2 subjects = 8 predictions, passed to model.predict in a single batch call
            assert len(results) == 8
            assert mock_predict.call_count == 1

        student_ids = {st.id for st in students}
        for r in results:
            assert r.student_id in student_ids
            assert r.status == "success"
            assert 0.0 <= r.predicted_percentage <= 100.0


@pytest.mark.django_db
class TestTakePredictionSnapshotsCommand:
    def test_command_idempotency_and_creation(self, active_model):
        """take_prediction_snapshots generates snapshots and updates them idempotently on re-run."""
        tree = make_university(students_per_batch=3)

        out = StringIO()
        call_command("take_prediction_snapshots", checkpoint="midterm_test", stdout=out)
        output = out.getvalue()
        assert "Successfully persisted 6 prediction snapshot(s)" in output

        # 3 students * 2 subjects = 6 snapshots
        assert PredictionSnapshot.objects.filter(checkpoint="midterm_test").count() == 6

        # Running again with the same checkpoint updates existing records idempotently
        out2 = StringIO()
        call_command("take_prediction_snapshots", checkpoint="midterm_test", stdout=out2)
        assert PredictionSnapshot.objects.filter(checkpoint="midterm_test").count() == 6
        assert "Successfully persisted" in out2.getvalue()


@pytest.mark.django_db
class TestScopedSnapshotsSelector:
    def test_scoped_snapshots_for_roles(self, active_model):
        tree = make_university(students_per_batch=3)
        call_command("take_prediction_snapshots", checkpoint="midterm_roles")

        # Teacher should see snapshots for students they teach (3 students * 2 subjects = 6)
        teacher_user = tree["teachers"][0].user
        teacher_qs, label = scoped_snapshots_for(teacher_user)
        assert teacher_qs.count() == 6

        # HOD should see all department snapshots
        hod_user = tree["hod"]
        hod_qs, label = scoped_snapshots_for(hod_user)
        assert hod_qs.count() == 6

        # Dean should see all school snapshots
        dean_user = tree["dean"]
        dean_qs, label = scoped_snapshots_for(dean_user)
        assert dean_qs.count() == 6

        # VC / Admin should see university snapshots
        vc_user = tree["executives"]["vc"]
        vc_qs, label = scoped_snapshots_for(vc_user)
        assert vc_qs.count() == 6

        # Student should only see their own snapshots
        student_user = tree["students"][0].user
        student_qs, label = scoped_snapshots_for(student_user)
        assert student_qs.count() == 2
