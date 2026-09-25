"""
ML Feature Contract & Attribute Governance for EduPulse.

This module defines the single, authoritative contract for machine learning features across
the platform. It guarantees that protected demographic attributes and unapproved socio-economic
proxy variables are strictly prohibited from entering any predictive model input pipeline.

IMPORTANT FAIRNESS & GOVERNANCE POLICY:
Protected attributes (such as gender, category, address_state, and learning_disabilities)
may still be READ by authorized staff for post-hoc parity audits, demographic representations,
and fairness reporting (Task A18). However, they MUST NEVER be fed as features or inputs into
any model training, fine-tuning, or inference workflow.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class FeatureSpec:
    """Specification of an approved machine learning feature."""
    name: str
    dtype: type
    unit: str
    min_value: float
    max_value: float
    source: str
    allowed_models: frozenset[str]  # e.g., frozenset({"baseline", "institute"})


# Protected demographic attributes: STRICTLY PROHIBITED as model inputs.
PROTECTED_ATTRIBUTES: frozenset[str] = frozenset({
    "gender",
    "category",
    "address_state",
    "learning_disabilities",
})

# Review-required proxy / background attributes: Excluded unless explicitly approved in docs/ML_CONTRACT.md.
REVIEW_REQUIRED: frozenset[str] = frozenset({
    "family_income",
    "parental_education_level",
    "distance_from_home",
    "internet_access",
    "access_to_resources",
})

# Approved features: EXACTLY matching docs/ML_CONTRACT.md Section 3.
# No other features may be defined here unless approved in docs/ML_CONTRACT.md.
FEATURES: dict[str, FeatureSpec] = {
    "attendance_percentage": FeatureSpec(
        name="attendance_percentage",
        dtype=float,
        unit="%",
        min_value=0.0,
        max_value=100.0,
        source="academics",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "hours_studied": FeatureSpec(
        name="hours_studied",
        dtype=float,
        unit="hours/week",
        min_value=0.0,
        max_value=168.0,
        source="habit_logs",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "sleep_hours": FeatureSpec(
        name="sleep_hours",
        dtype=float,
        unit="hours/day",
        min_value=0.0,
        max_value=24.0,
        source="habit_logs",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "previous_score": FeatureSpec(
        name="previous_score",
        dtype=float,
        unit="%",
        min_value=0.0,
        max_value=100.0,
        source="academics",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "tutoring_sessions": FeatureSpec(
        name="tutoring_sessions",
        dtype=int,
        unit="sessions/month",
        min_value=0.0,
        max_value=50.0,
        source="habit_logs",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "physical_activity": FeatureSpec(
        name="physical_activity",
        dtype=float,
        unit="hours/week",
        min_value=0.0,
        max_value=50.0,
        source="habit_logs",
        allowed_models=frozenset({"baseline", "institute"}),
    ),
    "internal_assessment_score": FeatureSpec(
        name="internal_assessment_score",
        dtype=float,
        unit="%",
        min_value=0.0,
        max_value=100.0,
        source="academics",
        allowed_models=frozenset({"institute"}),
    ),
}


def validate_feature_list(names: Sequence[str], model_kind: Optional[str] = None) -> bool:
    """
    Validates a list of candidate feature names against the ML contract.

    Raises:
        ValueError: If any feature name is protected, requires unapproved review,
                    is unrecognized, or is not permitted for the requested model_kind.

    Returns:
        bool: True if all feature names are valid.
    """
    for name in names:
        if name in PROTECTED_ATTRIBUTES:
            raise ValueError(
                f"Feature '{name}' is a protected attribute and strictly banned as model input."
            )
        if name in REVIEW_REQUIRED:
            raise ValueError(
                f"Feature '{name}' is a review-required attribute and not approved in docs/ML_CONTRACT.md."
            )
        if name not in FEATURES:
            raise ValueError(f"Unknown feature '{name}' not found in ML feature contract.")

        spec = FEATURES[name]
        if model_kind and model_kind not in spec.allowed_models:
            raise ValueError(
                f"Feature '{name}' is not permitted for model kind '{model_kind}'. "
                f"Allowed models: {sorted(spec.allowed_models)}"
            )

    return True


def validate_row(mapping: Mapping[str, Any]) -> list[str]:
    """
    Validates a single input sample row against feature types and value ranges.
    Returns a list of validation failure descriptions, or an empty list if valid.
    Never invents or fabricates default values for missing data.
    """
    problems: list[str] = []

    for name, value in mapping.items():
        if name in PROTECTED_ATTRIBUTES:
            problems.append(f"Row contains protected attribute '{name}'.")
            continue
        if name in REVIEW_REQUIRED:
            problems.append(f"Row contains unapproved review-required attribute '{name}'.")
            continue
        if name not in FEATURES:
            problems.append(f"Row contains unknown feature '{name}'.")
            continue

        if value is None:
            # Missing value reported without fabricating a fake default
            problems.append(f"Feature '{name}' value cannot be None.")
            continue

        spec = FEATURES[name]

        # Type validation (allowing int for float fields, but rejecting string/invalid types)
        if spec.dtype is float and not isinstance(value, (int, float)):
            problems.append(f"Feature '{name}' has invalid type {type(value).__name__}; expected float.")
            continue
        elif spec.dtype is int and not (isinstance(value, int) and not isinstance(value, bool)):
            problems.append(f"Feature '{name}' has invalid type {type(value).__name__}; expected int.")
            continue

        # Range validation
        num_val = float(value)
        if num_val < spec.min_value or num_val > spec.max_value:
            problems.append(
                f"Feature '{name}' value {value} is out of bounds; "
                f"must be between {spec.min_value} and {spec.max_value} {spec.unit}."
            )

    return problems
