"""
Dataset loader and feature assembler for Model B (Institute Model).
Extracts verified institutional records strictly from students with data_origin='real'.
Guarantees zero leakage and validates minimum dataset thresholds before training.
"""

from typing import Any, Optional, Tuple
import pandas as pd
import numpy as np
from django.conf import settings
from django.db.models import QuerySet

from academics.models import Result, SemesterResult
from predictions.selectors import training_rows, assert_real_training_data
from edupulse_ml.contract import validate_feature_list


class InsufficientDataError(Exception):
    """Raised when institutional records do not meet minimum training thresholds."""
    pass


def load_institute_dataset(
    queryset: Optional[QuerySet] = None,
    enforce_thresholds: bool = True,
    use_habits: Optional[bool] = None,
) -> pd.DataFrame:
    """
    Extracts and prepares institutional training data from Result records.

    Parameters:
        queryset: Optional custom QuerySet of Result objects (must have data_origin='real').
                  Defaults to predictions.selectors.training_rows().
        enforce_thresholds: If True, validates minimum students, rows, and semester count.
        use_habits: Whether to incorporate habit features (v2). Defaults to settings.MODEL_B_USE_HABITS.

    Returns:
        pd.DataFrame containing feature columns, target, group identifiers, and audit metadata.
    """
    if queryset is None:
        queryset = training_rows()

    # Enforce data origin guard: must be strictly real institutional data
    assert_real_training_data(queryset)

    results = list(
        queryset.select_related(
            "student",
            "student__user",
            "subject",
        )
    )

    if not results:
        if enforce_thresholds:
            raise InsufficientDataError("No verified real institutional records found for training.")
        return pd.DataFrame()

    # Bulk prefetch previous semester results for previous_score and attendance
    student_ids = {r.student_id for r in results}
    sem_results = SemesterResult.objects.filter(
        student_id__in=student_ids,
        student__data_origin="real",
    )
    # Map (student_id, semester) -> SemesterResult
    sem_map: dict[Tuple[int, int], SemesterResult] = {
        (sr.student_id, sr.semester): sr for sr in sem_results
    }

    rows = []
    for r in results:
        # Calculate target percentage
        max_marks = float(r.max_marks or 100.0)
        total_sec = float(r.total_secured or 0.0)
        target_pct = (total_sec / max_marks) * 100.0 if max_marks > 0 else 0.0

        # Previous semester academic standing
        prev_sem = r.semester - 1
        prev_record = sem_map.get((r.student_id, prev_sem))
        current_record = sem_map.get((r.student_id, r.semester))

        previous_score = None
        if prev_record and prev_record.percentage:
            previous_score = float(prev_record.percentage)
        elif prev_record and prev_record.sgpa:
            previous_score = float(prev_record.sgpa * 10.0)

        # Attendance from official SemesterResult records
        attendance = None
        if current_record and current_record.attendance_percentage is not None:
            attendance = float(current_record.attendance_percentage)
        elif prev_record and prev_record.attendance_percentage is not None:
            attendance = float(prev_record.attendance_percentage)

        # Internal assessment score percentage
        int_max = float(getattr(r.subject, "internal_max", 0) or 0)
        int_marks = float(r.internal_marks or 0.0)
        if int_max > 0:
            internal_pct = (int_marks / int_max) * 100.0
        else:
            internal_pct = 0.0

        row_dict: dict[str, Any] = {
            "student_id": r.student_id,
            "semester": r.semester,
            "subject_id": r.subject_id,
            "subject_code": r.subject.code if r.subject else "",
            # Approved Model B features
            "attendance_percentage": attendance,
            "previous_score": previous_score,
            "internal_assessment_score": internal_pct,
            # Target
            "target_percentage": float(np.clip(target_pct, 0.0, 100.0)),
            # Protected demographic attributes for audit-only fairness reports (NEVER used in training)
            "gender": getattr(r.student.user, "gender", None),
            "category": getattr(r.student.user, "category", None),
        }

        # Habit telemetry if enabled (v2)
        if use_habits:
            hours_studied = getattr(current_record, "hours_studied_per_week", None) if current_record else None
            sleep_hours = getattr(current_record, "sleep_hours_per_night", None) if current_record else None
            tutoring = getattr(current_record, "tutoring_sessions", None) if current_record else None
            phys_act = getattr(current_record, "physical_activity", None) if current_record else None

            row_dict["hours_studied"] = hours_studied
            row_dict["sleep_hours"] = sleep_hours
            row_dict["tutoring_sessions"] = tutoring
            row_dict["physical_activity"] = phys_act

        rows.append(row_dict)

    df = pd.DataFrame(rows)

    # Filter out rows with incomplete required academic features
    # (Never invent or impute missing historical values)
    df = df.dropna(subset=["attendance_percentage", "previous_score", "internal_assessment_score"])

    if enforce_thresholds:
        validate_institute_thresholds(df)

    return df


def validate_institute_thresholds(df: pd.DataFrame) -> None:
    """
    Validates minimum dataset size requirements for Model B.
    Raises InsufficientDataError if any threshold is violated.
    """
    min_students = getattr(settings, "MODEL_B_MIN_STUDENTS", 200)
    min_rows = getattr(settings, "MODEL_B_MIN_ROWS", 1000)
    min_semesters = getattr(settings, "MODEL_B_MIN_SEMESTERS", 3)

    n_students = df["student_id"].nunique() if not df.empty and "student_id" in df.columns else 0
    n_rows = len(df)
    n_semesters = df["semester"].nunique() if not df.empty and "semester" in df.columns else 0

    reasons = []
    if n_students < min_students:
        reasons.append(f"Distinct students ({n_students}) < minimum required ({min_students})")
    if n_rows < min_rows:
        reasons.append(f"Total training rows ({n_rows}) < minimum required ({min_rows})")
    if n_semesters < min_semesters:
        reasons.append(f"Distinct historical semesters ({n_semesters}) < minimum required ({min_semesters})")

    if reasons:
        raise InsufficientDataError(
            f"Insufficient institutional data to train Model B:\n - " + "\n - ".join(reasons)
        )
