"""
Plain-language prediction explanations and factor attribution for EduPulse.
Computes per-prediction directional contributions for linear models and global factor
importance for non-linear models without exposing protected demographic attributes.
"""

from typing import Any, Mapping, Optional, Sequence
import numpy as np

from edupulse_ml.contract import PROTECTED_ATTRIBUTES

FEATURE_HUMAN_NAMES: dict[str, str] = {
    "attendance_percentage": "Classroom Attendance",
    "previous_score": "Prior Academic Standing",
    "internal_assessment_score": "Mid-term Assessment Performance",
    "hours_studied": "Weekly Study Hours",
    "sleep_hours": "Sleep Routine",
    "tutoring_sessions": "Tutoring Support",
    "physical_activity": "Physical Activity",
}


def explain_prediction(
    model: Any,
    feature_names: Sequence[str],
    feature_values: Mapping[str, Any],
    model_version: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Computes top explanatory factors for a given prediction.

    - For linear models (e.g., Ridge inside a Pipeline):
      Calculates per-prediction directional contributions (coefficient * standardized value deviation)
      for the top 3 contributing factors.
    - For non-linear models:
      Returns top global factors and explicitly notes that per-student attribution is unavailable.
    - STRICT GOVERNANCE RULE: Protected attributes (gender, category, etc.) are NEVER returned.

    Parameters:
        model: Loaded model estimator or pipeline.
        feature_names: Sequence of feature names expected by the model.
        feature_values: Dict mapping feature name to its value for this sample.
        model_version: Optional ModelVersion instance containing metadata/metrics.

    Returns:
        list[dict[str, Any]]: Up to 3 explanatory factor dictionaries.
    """
    # 1. Filter out any protected attributes
    safe_features = [f for f in feature_names if f not in PROTECTED_ATTRIBUTES]
    if not safe_features:
        return []

    # Check for missing values in feature_values
    missing = [f for f in safe_features if feature_values.get(f) is None]
    if missing:
        return [
            {
                "feature": "missing_data",
                "name": "Insufficient Data",
                "impact": "N/A",
                "direction": "neutral",
                "description": f"Missing required telemetry: {', '.join(missing)}.",
            }
        ]

    # 2. Linear Model Inspection (e.g. Ridge standalone or in Pipeline)
    regressor = None
    scaler = None

    if hasattr(model, "named_steps"):
        # Scikit-learn Pipeline
        for step_name, step_obj in model.named_steps.items():
            if hasattr(step_obj, "coef_"):
                regressor = step_obj
            elif hasattr(step_obj, "mean_") and hasattr(step_obj, "scale_"):
                scaler = step_obj
    elif hasattr(model, "coef_"):
        regressor = model

    if regressor is not None and hasattr(regressor, "coef_"):
        raw_coefs = np.asarray(regressor.coef_).ravel()
        if len(raw_coefs) == len(safe_features):
            contributions = []
            for idx, fname in enumerate(safe_features):
                val = float(feature_values.get(fname, 0.0) or 0.0)
                mean_val = float(scaler.mean_[idx]) if scaler is not None and hasattr(scaler, "mean_") else 50.0
                scale_val = float(scaler.scale_[idx]) if scaler is not None and hasattr(scaler, "scale_") and scaler.scale_[idx] != 0 else 1.0
                coef = float(raw_coefs[idx])

                # Normalized deviation contribution
                contrib = coef * ((val - mean_val) / scale_val)
                contributions.append((fname, contrib, val))

            # Sort by absolute contribution descending
            contributions.sort(key=lambda item: abs(item[1]), reverse=True)
            top_factors = contributions[:3]

            factors = []
            for fname, contrib, val in top_factors:
                human_name = FEATURE_HUMAN_NAMES.get(fname, fname.replace("_", " ").title())
                direction = "positive" if contrib > 0.05 else ("negative" if contrib < -0.05 else "neutral")
                impact_pct = f"{contrib:+.1f}%"
                direction_word = "Positive" if direction == "positive" else ("Negative" if direction == "negative" else "Neutral")

                factors.append({
                    "feature": fname,
                    "name": human_name,
                    "impact": impact_pct,
                    "direction": direction,
                    "description": f"{direction_word} influence from {human_name} ({impact_pct}).",
                })
            return factors

    # 3. Non-Linear Model Fallback (e.g., HistGradientBoostingRegressor)
    # Check if global importances are stored in model_version.metrics
    metrics = getattr(model_version, "metrics", {}) or {}
    global_importances = metrics.get("global_feature_importance", {})

    ranked_features = safe_features
    if global_importances and isinstance(global_importances, dict):
        ranked_features = sorted(
            safe_features,
            key=lambda f: global_importances.get(f, 0.0),
            reverse=True,
        )

    factors = []
    for fname in ranked_features[:3]:
        human_name = FEATURE_HUMAN_NAMES.get(fname, fname.replace("_", " ").title())
        factors.append({
            "feature": fname,
            "name": human_name,
            "impact": "Global factor",
            "direction": "neutral",
            "description": f"Global influence on model decisions (per-student attribution is unavailable).",
        })

    return factors
