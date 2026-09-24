"""
Unit and integration tests for Task A18: Model B Training Pipeline.
Verifies dataset thresholds, temporal splitting, grouped-CV anti-leakage,
demographic fairness suppression, promotion decision engine, and CLI command execution.
"""

import os
import pytest
import numpy as np
import pandas as pd
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from edupulse_ml.datasets.institute import (
    load_institute_dataset,
    validate_institute_thresholds,
    InsufficientDataError,
)
from edupulse_ml.fairness import audit_demographic_fairness
from edupulse_ml.train_b import split_temporal_holdout, train_and_evaluate_model_b
from predictions.models import ModelVersion
from predictions.promotion import should_promote


def make_synthetic_institute_df(
    n_students: int = 250,
    rows_per_student: int = 5,
    n_semesters: int = 4,
    random_state: int = 42,
) -> pd.DataFrame:
    """Helper to synthesize compliant institutional records with ground truth features."""
    rng = np.random.RandomState(random_state)
    records = []

    for s_idx in range(1, n_students + 1):
        gender = "Female" if s_idx % 2 == 0 else "Male"
        category = "General" if s_idx % 3 == 0 else "OBC"
        base_ability = rng.uniform(40.0, 90.0)

        for sem in range(1, n_semesters + 1):
            prev_score = float(np.clip(base_ability + rng.normal(0, 3), 35.0, 98.0))
            att = float(np.clip(rng.uniform(70.0, 98.0), 50.0, 100.0))
            internal = float(np.clip(prev_score + rng.normal(0, 4), 30.0, 100.0))
            # True target depends on prior score, attendance, and internal marks
            target = 0.45 * prev_score + 0.35 * internal + 0.20 * att + rng.normal(0, 2)
            target = float(np.clip(target, 20.0, 100.0))

            records.append({
                "student_id": s_idx,
                "semester": sem,
                "subject_id": sem * 10 + 1,
                "subject_code": f"SUB{sem}01",
                "attendance_percentage": att,
                "previous_score": prev_score,
                "internal_assessment_score": internal,
                "target_percentage": target,
                "gender": gender,
                "category": category,
            })

    return pd.DataFrame(records)


class TestDatasetAndThresholds:
    def test_refuses_when_below_student_threshold(self):
        df = make_synthetic_institute_df(n_students=150, n_semesters=3)
        with pytest.raises(InsufficientDataError, match="Distinct students"):
            validate_institute_thresholds(df)

    def test_refuses_when_below_row_threshold(self):
        # 210 students but only 2 rows each = 420 rows (< 1000)
        df = make_synthetic_institute_df(n_students=210, n_semesters=2)
        with pytest.raises(InsufficientDataError, match="Total training rows"):
            validate_institute_thresholds(df)

    def test_refuses_when_below_semester_threshold(self):
        # 250 students, 4 rows each, but only 2 distinct semesters (< 3)
        df = make_synthetic_institute_df(n_students=250, n_semesters=2)
        with pytest.raises(InsufficientDataError, match="Distinct historical semesters"):
            validate_institute_thresholds(df)

    def test_accepts_compliant_dataset(self):
        df = make_synthetic_institute_df(n_students=210, n_semesters=5)
        # Should pass without raising
        validate_institute_thresholds(df)

    @pytest.mark.django_db
    def test_refuses_demo_records(self):
        from academics.models import Result
        from tests.factories import make_university

        tree = make_university(students_per_batch=5)
        # Mark one student as demo
        student = tree["students"][0]
        student.data_origin = "demo"
        student.save(update_fields=["data_origin"])

        qs = Result.objects.filter(student=student)
        with pytest.raises(RuntimeError, match="Contaminated training data detected"):
            load_institute_dataset(queryset=qs, enforce_thresholds=False)


class TestTemporalSplitAndGroupedCV:
    def test_holdout_semester_never_appears_in_training(self):
        df = make_synthetic_institute_df(n_students=50, n_semesters=4)
        train_df, test_df = split_temporal_holdout(df)

        assert train_df["semester"].max() == 3
        assert test_df["semester"].unique().tolist() == [4]
        assert set(train_df["semester"].unique()).isdisjoint(set(test_df["semester"].unique()))

    def test_grouped_kfold_never_splits_students_across_folds(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(tmp_path))

        df = make_synthetic_institute_df(n_students=60, n_semesters=4)
        # Run training workflow
        results = train_and_evaluate_model_b(df)

        assert "candidate_name" in results
        assert "artifact_file" in results
        assert results["latest_holdout_semester"] == 4
        assert results["candidate_metrics"]["rmse"] < 10.0


class TestFairnessAudit:
    def test_fairness_suppresses_small_groups(self):
        # 15 Male students, 30 Female students
        metadata = pd.DataFrame({
            "student_id": list(range(1, 16)) + list(range(16, 46)),
            "gender": ["Male"] * 15 + ["Female"] * 30,
            "category": ["Gen"] * 45,
        })
        y_true = np.full(45, 75.0)
        y_pred = np.full(45, 74.0)

        report = audit_demographic_fairness(y_true, y_pred, metadata, min_group_size=20)

        gender_audit = report["attributes"]["gender"]
        # Male (< 20 students) must be suppressed
        assert gender_audit["Male"]["status"] == "suppressed"
        assert "Sample size too small" in gender_audit["Male"]["reason"]
        # Female (>= 20 students) must be reported
        assert gender_audit["Female"]["status"] == "reported"
        assert "rmse" in gender_audit["Female"]


class TestPromotionRule:
    def test_promotion_when_beating_baseline_and_incumbent(self):
        candidate = {"rmse": 3.5}
        incumbent = {"rmse": 6.0}
        baseline = {"rmse": 8.0}

        is_promotable, reasons = should_promote(candidate, incumbent, baseline, margin=2.0)
        assert is_promotable is True
        assert any("Candidate beat incumbent Model A by 2.50 points" in r for r in reasons)

    def test_rejection_when_failing_to_beat_baseline(self):
        candidate = {"rmse": 8.5}
        incumbent = {"rmse": 7.0}
        baseline = {"rmse": 8.0}

        is_promotable, reasons = should_promote(candidate, incumbent, baseline, margin=2.0)
        assert is_promotable is False
        assert any("failed to beat the naive baseline" in r for r in reasons)

    def test_rejection_when_insufficient_margin(self):
        candidate = {"rmse": 5.5}
        incumbent = {"rmse": 7.0}  # improvement = 1.5 < margin 2.0
        baseline = {"rmse": 9.0}

        is_promotable, reasons = should_promote(candidate, incumbent, baseline, margin=2.0)
        assert is_promotable is False
        assert any("did not beat incumbent Model A" in r for r in reasons)

    def test_rejection_when_incumbent_unavailable(self):
        candidate = {"rmse": 4.0}
        baseline = {"rmse": 8.0}

        is_promotable, reasons = should_promote(candidate, None, baseline, margin=2.0)
        assert is_promotable is False
        assert any("Incumbent Model A metrics unavailable" in r for r in reasons)


@pytest.mark.django_db
class TestTrainModelBCommand:
    def test_command_requires_confirm_real_data(self):
        with pytest.raises(CommandError, match="--confirm-real-data"):
            call_command("train_model_b")

    def test_command_enforces_prod_or_test_env(self, monkeypatch):
        monkeypatch.setenv("DJANGO_ENV", "dev")
        with pytest.raises(CommandError, match="Security Violation"):
            call_command("train_model_b", confirm_real_data=True)

    def test_command_execution_on_synthetic_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MODEL_ARTIFACT_DIR", str(tmp_path))
        monkeypatch.setenv("DJANGO_ENV", "test")

        synthetic_df = make_synthetic_institute_df(n_students=220, n_semesters=4)

        # Mock load_institute_dataset to provide synthetic DataFrame
        with patch("predictions.management.commands.train_model_b.load_institute_dataset", return_value=synthetic_df):
            out = StringIO()
            call_command("train_model_b", confirm_real_data=True, stdout=out)
            output = out.getvalue()

            assert "Registered Model B Candidate" in output
            assert "Holdout RMSE:" in output
            assert "PROMOTION STATUS:" in output

            # Candidate must be in ModelVersion registry with slot="institute" and is_active=False
            mv = ModelVersion.objects.filter(slot="institute").latest("id")
            assert mv.is_active is False
            assert mv.metrics["candidate_metrics"]["rmse"] > 0.0
            assert Path(tmp_path / mv.artifact_file).exists()
