"""
Grading criteria and risk-band classification logic.
Uses settings.PASS_MARK_PERCENT (40.0%) as the authoritative source of truth.
"""

from typing import Any, Optional, Sequence
from django.conf import settings

PASS_MARK_PERCENT = getattr(settings, "PASS_MARK_PERCENT", 40.0)

RISK_BAND_LOW = "low"
RISK_BAND_MEDIUM = "medium"
RISK_BAND_HIGH = "high"
RISK_BAND_INSUFFICIENT_DATA = "insufficient_data"

RISK_BANDS = (
    RISK_BAND_LOW,
    RISK_BAND_MEDIUM,
    RISK_BAND_HIGH,
    RISK_BAND_INSUFFICIENT_DATA,
)


def risk_band_for(
    predicted_percentage: Optional[float],
    missing_features: Optional[Sequence[str]] = None,
) -> str:
    """
    Computes categorical risk band from a predicted score and input completeness:
    - 'insufficient_data': Required features are missing or score is None.
    - 'high': Predicted score is below PASS_MARK_PERCENT (< 40.0%).
    - 'medium': Predicted score is passing but moderate (40.0% to 59.9%).
    - 'low': Predicted score is solid (>= 60.0%).
    """
    if missing_features or predicted_percentage is None:
        return RISK_BAND_INSUFFICIENT_DATA

    pass_mark = getattr(settings, "PASS_MARK_PERCENT", PASS_MARK_PERCENT)

    if predicted_percentage < pass_mark:
        return RISK_BAND_HIGH
    elif predicted_percentage < 60.0:
        return RISK_BAND_MEDIUM
    else:
        return RISK_BAND_LOW


def is_at_risk(
    predicted_percentage_or_band: Any,
    missing_features: Optional[Sequence[str]] = None,
) -> bool:
    """
    Returns True if the student/subject requires intervention.
    Accepts either a numeric predicted percentage or a string risk band.
    Includes both high-risk trajectories (< 40%) and insufficient telemetry data.
    """
    if isinstance(predicted_percentage_or_band, str):
        return predicted_percentage_or_band.lower() in (RISK_BAND_HIGH, RISK_BAND_INSUFFICIENT_DATA)
    band = risk_band_for(predicted_percentage_or_band, missing_features=missing_features)
    return band in (RISK_BAND_HIGH, RISK_BAND_INSUFFICIENT_DATA)


def letter_grade_for(percentage: Optional[float]) -> str:
    """
    Translates percentage score to standard UGC 10-point grade letter.
    """
    if percentage is None:
        return "F"
    if percentage >= 90.0:
        return "O"
    elif percentage >= 80.0:
        return "A+"
    elif percentage >= 70.0:
        return "A"
    elif percentage >= 60.0:
        return "B+"
    elif percentage >= 50.0:
        return "B"
    elif percentage >= getattr(settings, "PASS_MARK_PERCENT", PASS_MARK_PERCENT):
        return "C"
    else:
        return "F"
