"""
Training data selectors and data contamination guards for EduPulse machine learning.
Guarantees that institutional models are trained strictly on verified real-world institutional data (data_origin='real').
Synthetic demo or seeded records are strictly barred from all model training pipelines.
"""

from typing import Union
import pandas as pd
from django.db.models import QuerySet
from academics.models import Result


def training_rows(allow_demo: bool = False) -> QuerySet[Result]:
    """
    Returns an academic Result queryset filtered strictly to students with data_origin='real'.

    Raises:
        RuntimeError: If allow_demo is set to True or attempted in any training context.
    """
    if allow_demo:
        raise RuntimeError(
            "Security Violation: Training data selector strictly prohibits demo data. "
            "Models must never be trained on synthetic or seeded demonstration records."
        )

    return (
        Result.objects.filter(student__data_origin="real")
        .select_related("student", "student__user", "subject", "student__course")
        .order_by("student_id", "semester", "subject_id")
    )


def assert_real_training_data(data: Union[QuerySet, pd.DataFrame]) -> bool:
    """
    Guards model training pipelines by verifying that every record in the provided
    queryset or DataFrame belongs to verified real-world institutional data.

    Raises:
        RuntimeError: If any row belongs to a student with data_origin != 'real'.

    Returns:
        bool: True if all data is verified real.
    """
    if isinstance(data, QuerySet):
        model_cls = data.model
        if hasattr(model_cls, "data_origin"):
            contaminated_count = data.exclude(data_origin="real").count()
        elif hasattr(model_cls, "student"):
            contaminated_count = data.exclude(student__data_origin="real").count()
        else:
            raise TypeError(f"Cannot verify data_origin on queryset of model {model_cls.__name__}")

        if contaminated_count > 0:
            raise RuntimeError(
                f"Contaminated training data detected: {contaminated_count} record(s) "
                f"do not have data_origin='real'. Refusing to proceed with model training."
            )
    elif isinstance(data, pd.DataFrame):
        if "data_origin" in data.columns:
            non_real = data[data["data_origin"] != "real"]
            if len(non_real) > 0:
                raise RuntimeError(
                    f"Contaminated training data detected: {len(non_real)} row(s) "
                    f"in DataFrame do not have data_origin='real'."
                )
    else:
        raise TypeError(f"Expected QuerySet or DataFrame, got {type(data).__name__}")

    return True


def scoped_snapshots_for(user) -> tuple[QuerySet, str]:
    """
    Returns (snapshots_queryset, scope_label) adhering to the academic organizational hierarchy.
    Enforces strict object-level access boundaries in a single database query.
    """
    from .models import PredictionSnapshot

    role = getattr(user, "role", None)

    if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN") or getattr(user, "is_superuser", False):
        return PredictionSnapshot.objects.all(), "Entire University"

    if role == "DEAN":
        school_id = getattr(user, "school_id", None)
        if school_id:
            qs = PredictionSnapshot.objects.filter(student__course__department__school_id=school_id)
            label = f"School: {user.school}"
        else:
            qs = PredictionSnapshot.objects.none()
            label = "Your School (Unassigned)"
        return qs, label

    if role == "HOD":
        dept_id = getattr(user, "department_id", None)
        if dept_id:
            qs = PredictionSnapshot.objects.filter(student__course__department_id=dept_id)
            label = f"Department: {user.department}"
        else:
            qs = PredictionSnapshot.objects.none()
            label = "Your Department (Unassigned)"
        return qs, label

    if role == "TEACHER":
        qs = PredictionSnapshot.objects.filter(student__results__teacher__user_id=user.id).distinct()
        return qs, "Students you teach"

    if role == "STUDENT":
        qs = PredictionSnapshot.objects.filter(student__user_id=user.id)
        return qs, "Your Academic Forecast"

    return PredictionSnapshot.objects.none(), "No Scope"
