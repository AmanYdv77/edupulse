"""
Service layer for loading machine learning models and generating score predictions.
Enforces artifact path sandboxing, runtime library compatibility, and strict data validation.
Provides true batch inference (services.predict_for_students) for constant query counts.
"""

from dataclasses import dataclass
from datetime import timedelta
import logging
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import joblib
import pandas as pd
import sklearn
from django.conf import settings
from django.utils import timezone
from edupulse_ml.contract import validate_feature_list, validate_row
from .models import ModelVersion
from .grades import PASS_MARK_PERCENT, RISK_BAND_INSUFFICIENT_DATA, risk_band_for, is_at_risk

logger = logging.getLogger(__name__)


class IncompatibleEnvironmentError(Exception):
    """Raised when the serialized model artifact was built with an incompatible library version."""
    pass


class ModelNotFoundError(Exception):
    """Raised when no active ModelVersion is registered for the requested slot."""
    pass


def resolve_artifact_path(artifact_file: str) -> Path:
    """
    Resolves artifact_file strictly inside settings.MODEL_ARTIFACT_DIR.
    Rejects any path separators ('/', '\\') or directory traversal ('..').

    SECURITY WARNING:
    joblib and pickle files deserialize Python objects by executing arbitrary code.
    Model artifact files must NEVER be retrieved or loaded from untrusted,
    unauthenticated, or user-supplied external sources.
    """
    if not artifact_file or not isinstance(artifact_file, str):
        raise ValueError("artifact_file must be a non-empty string.")

    if "/" in artifact_file or "\\" in artifact_file or ".." in artifact_file:
        raise ValueError(
            f"Path escape attempt detected: '{artifact_file}' contains invalid directory navigation."
        )

    base_dir = Path(settings.MODEL_ARTIFACT_DIR).resolve()
    resolved = (base_dir / artifact_file).resolve()

    if resolved.parent != base_dir:
        raise ValueError(
            f"Artifact path '{resolved}' escapes the configured artifact directory '{base_dir}'."
        )

    return resolved


@dataclass(frozen=True)
class PredictionResult:
    """
    Structured outcome of a machine learning forecast for a single student-subject pair.
    Implements key-based dictionary access for backwards compatibility with legacy templates.
    """
    student_id: int
    student_roll_no: str
    subject_id: int
    subject_code: str
    subject_title: str
    subject_credits: int
    semester: int
    predicted_percentage: Optional[float]
    risk_band: str
    is_at_risk: bool
    reasons: list[str]
    features: dict[str, Any]
    model_version_id: Optional[int]

    @property
    def status(self) -> str:
        return "insufficient_data" if self.predicted_percentage is None else "success"

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class PredictorService:
    """
    Inference service managing cached model lifecycles and strictly validated predictions.
    """

    _cache: dict[int, Any] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory loaded model cache."""
        cls._cache.clear()

    @classmethod
    def get_active_model_version(cls, slot: str) -> Optional[ModelVersion]:
        """Returns the currently active ModelVersion for the given slot, or None."""
        return ModelVersion.objects.filter(slot=slot, is_active=True).first()

    @classmethod
    def load(cls, slot: str) -> Any:
        """
        Loads and returns the active model for the given slot.
        Verifies scikit-learn version compatibility, validates feature contract,
        and resolves the artifact path inside the secure artifact directory.
        Caches the model instance per process keyed by ModelVersion id.
        """
        model_version = cls.get_active_model_version(slot)
        if not model_version:
            raise ModelNotFoundError(f"No active model found for slot '{slot}'.")

        if model_version.id in cls._cache:
            return cls._cache[model_version.id]

        # 1. Compatibility check: refuse mismatched scikit-learn version
        current_sklearn = sklearn.__version__
        if model_version.sklearn_version != current_sklearn:
            err_msg = (
                f"ModelVersion id={model_version.id} ({model_version.slot} v{model_version.version}) "
                f"was trained with scikit-learn '{model_version.sklearn_version}', but current runtime "
                f"is '{current_sklearn}'. Refusing to load incompatible model."
            )
            logger.error(err_msg)
            raise IncompatibleEnvironmentError(err_msg)

        # 2. ML Contract validation: verify features adhere to governance
        validate_feature_list(model_version.feature_names, model_kind=slot)

        # 3. Path resolution & safety
        artifact_path = resolve_artifact_path(model_version.artifact_file)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact file not found at '{artifact_path}'.")

        # 4. Load artifact and cache
        loaded_model = joblib.load(artifact_path)
        cls._cache[model_version.id] = loaded_model
        return loaded_model

    @classmethod
    def predict(cls, slot: str, rows: Sequence[Mapping[str, Any]]) -> list[dict]:
        """
        Generates score forecasts for a collection of sample rows in a single batch.
        Validates every row with validate_row; NEVER invents or substitutes default numbers.
        Returns per-row results with predicted percentage or an 'insufficient_data' reason.
        """
        model_version = cls.get_active_model_version(slot)
        if not model_version:
            raise ModelNotFoundError(f"No active model found for slot '{slot}'.")

        model = cls.load(slot)
        feature_names = model_version.feature_names
        results = [None] * len(rows)

        batch_indices = []
        batch_rows = []

        for idx, row in enumerate(rows):
            problems = validate_row(row)

            # Check that every expected feature exists in the input row
            missing_features = [f for f in feature_names if f not in row or row[f] is None]
            if missing_features:
                problems.append(f"Missing required features: {missing_features}")

            if problems:
                results[idx] = {
                    "status": "insufficient_data",
                    "problems": problems,
                }
            else:
                batch_indices.append(idx)
                batch_rows.append({f: row[f] for f in feature_names})

        # Single batch prediction across all valid rows
        if batch_rows:
            input_df = pd.DataFrame(batch_rows)[feature_names]
            raw_predictions = model.predict(input_df)

            for idx, raw_prediction in zip(batch_indices, raw_predictions):
                score = max(0.0, min(100.0, float(raw_prediction)))
                results[idx] = {
                    "status": "success",
                    "predicted_percentage": round(score, 1),
                    "is_at_risk": score < PASS_MARK_PERCENT,
                }

        return results


def predict_for_students(
    students: Sequence[Any],
    semester: Optional[int] = None,
    model_version: Optional[ModelVersion] = None,
    slot: str = "baseline",
) -> list[PredictionResult]:
    """
    Executes true batch machine learning inference across multiple students and subjects.
    Builds ONE single unified feature matrix DataFrame and invokes model.predict() EXACTLY ONCE.
    Never invents or substitutes default numbers for missing telemetry.
    """
    student_list = list(students)
    if not student_list:
        return []

    if model_version is None:
        model_version = PredictorService.get_active_model_version(slot)

    # Return empty list when no prediction model is active (displays "No active model" in UI)
    if not model_version:
        return []

    from academics.models import Subject, SemesterResult, HabitCheckInLog
    from academics.services.habits import compute_habit_summary_from_logs

    # 1. Bulk prefetch subjects for all relevant courses and target semesters
    course_ids = {s.course_id for s in student_list if s.course_id}
    target_semesters = {semester or s.current_semester for s in student_list}

    subjects_qs = Subject.objects.filter(
        course_id__in=course_ids,
        semester__in=target_semesters,
    ).select_related("course")

    subjects_by_course_sem: dict[tuple[int, int], list[Subject]] = {}
    for subj in subjects_qs:
        key = (subj.course_id, subj.semester)
        subjects_by_course_sem.setdefault(key, []).append(subj)

    # 2. Bulk prefetch latest SemesterResult for each student
    student_ids = [s.id for s in student_list]
    prior_results_qs = SemesterResult.objects.filter(
        student_id__in=student_ids
    ).order_by("student_id", "-semester")

    latest_sem_by_student: dict[int, SemesterResult] = {}
    for sr in prior_results_qs:
        if sr.student_id not in latest_sem_by_student:
            latest_sem_by_student[sr.student_id] = sr

    # 3. Bulk prefetch recent habit logs for rolling telemetry calculation (28 days)
    today = timezone.now().date()
    cutoff = today - timedelta(days=28)
    logs_qs = HabitCheckInLog.objects.filter(
        student_id__in=student_ids,
        log_date__gte=cutoff,
    ).order_by("student_id", "-log_date", "-id")

    logs_by_student: dict[int, list[HabitCheckInLog]] = {}
    for log in logs_qs:
        logs_by_student.setdefault(log.student_id, []).append(log)

    results: list[PredictionResult] = []
    batch_queue = []
    batch_rows = []

    for s in student_list:
        target_sem = semester or s.current_semester
        subjs = subjects_by_course_sem.get((s.course_id, target_sem), [])
        sr = latest_sem_by_student.get(s.id)
        habits = compute_habit_summary_from_logs(logs_by_student.get(s.id, []))

        # Build feature vector without fabricating defaults
        attendance = sr.attendance_percentage if sr and sr.attendance_percentage is not None else None
        prev_score = sr.percentage if sr and sr.percentage is not None else None
        hours_studied = habits.hours_studied_per_week if habits and habits.hours_studied_per_week is not None else (sr.hours_studied_per_week if sr else None)
        sleep_hours = habits.sleep_hours_per_night if habits and habits.sleep_hours_per_night is not None else (sr.sleep_hours_per_night if sr else None)
        tutoring = habits.tutoring_sessions if habits and habits.tutoring_sessions is not None else (sr.tutoring_sessions if sr else None)
        physical = habits.physical_activity if habits and habits.physical_activity is not None else (sr.physical_activity if sr else None)

        feature_row = {
            "attendance_percentage": attendance,
            "hours_studied": hours_studied,
            "sleep_hours": sleep_hours,
            "previous_score": prev_score,
            "tutoring_sessions": tutoring,
            "physical_activity": physical,
        }

        # Check for missing required features
        missing_features = [f for f in model_version.feature_names if f not in feature_row or feature_row[f] is None]

        for subj in subjs:
            if missing_features:
                results.append(
                    PredictionResult(
                        student_id=s.id,
                        student_roll_no=s.roll_no,
                        subject_id=subj.id,
                        subject_code=subj.code,
                        subject_title=subj.title,
                        subject_credits=subj.credits,
                        semester=target_sem,
                        predicted_percentage=None,
                        risk_band=RISK_BAND_INSUFFICIENT_DATA,
                        is_at_risk=True,
                        reasons=[f"Missing required telemetry: {', '.join(missing_features)}"],
                        features=feature_row,
                        model_version_id=model_version.id,
                    )
                )
            else:
                batch_queue.append((s, subj, target_sem, feature_row))
                batch_rows.append(feature_row)

    # 4. SINGLE MATRIX PREDICTION CALL
    if batch_rows:
        model = PredictorService.load(model_version.slot)
        input_df = pd.DataFrame(batch_rows)[model_version.feature_names]
        raw_preds = model.predict(input_df)

        for (s, subj, sem_num, feats), raw_pred in zip(batch_queue, raw_preds):
            score = max(0.0, min(100.0, round(float(raw_pred), 1)))
            band = risk_band_for(score)
            risk = is_at_risk(score)
            reasons = []
            if risk:
                reasons.append(
                    f"Predicted score {score}% is below academic pass threshold ({PASS_MARK_PERCENT}%)"
                )

            results.append(
                PredictionResult(
                    student_id=s.id,
                    student_roll_no=s.roll_no,
                    subject_id=subj.id,
                    subject_code=subj.code,
                    subject_title=subj.title,
                    subject_credits=subj.credits,
                    semester=sem_num,
                    predicted_percentage=score,
                    risk_band=band,
                    is_at_risk=risk,
                    reasons=reasons,
                    features=feats,
                    model_version_id=model_version.id,
                )
            )

    return sorted(results, key=lambda r: (r.student_id, r.subject_code))


def predict_current_subjects(student: Any) -> list[PredictionResult]:
    """
    Convenience backward-compatible adapter predicting current semester subjects for a single student.
    Delegates to the batch engine with a one-element list.
    """
    return predict_for_students([student])
