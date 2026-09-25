"""
Fairness and disparity auditing for EduPulse machine learning models.
Analyzes residual error and pass/fail prediction distributions across protected demographic cohorts.

IMPORTANT ETHICAL & GOVERNANCE RULES:
1. Protected attributes (gender, category) are READ SOLELY within this audit module.
   They are NEVER used as features, inputs, or conditioning variables in any model.
2. Privacy & Statistical Validity Guard: Any group with fewer than 20 students is
   STRICTLY SUPPRESSED to prevent re-identification and statistical distortion.
3. Audit outputs are written exclusively to offline artifact storage;
   they are NEVER exposed in student/faculty operational UIs or written to the primary database.
"""

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def audit_demographic_fairness(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    metadata: pd.DataFrame,
    min_group_size: int = 20,
    pass_mark: float = 40.0,
) -> dict[str, Any]:
    """
    Computes disaggregated regression and classification error metrics across protected demographic groups.

    Parameters:
        y_true: True test set scores (0-100).
        y_pred: Predicted test set scores (0-100).
        metadata: DataFrame containing 'student_id', 'gender', and 'category' for each test sample.
        min_group_size: Minimum distinct student count required to report group metrics (default: 20).
        pass_mark: Passing score percentage threshold.

    Returns:
        dict: Hierarchical audit report with overall and subgroup breakdown metrics.
    """
    y_true_arr = np.clip(np.asarray(y_true, dtype=float), 0.0, 100.0)
    y_pred_arr = np.clip(np.asarray(y_pred, dtype=float), 0.0, 100.0)

    if len(y_true_arr) != len(metadata):
        raise ValueError(
            f"Length mismatch: {len(y_true_arr)} predictions vs {len(metadata)} metadata rows."
        )

    eval_df = metadata.copy()
    eval_df["y_true"] = y_true_arr
    eval_df["y_pred"] = y_pred_arr
    eval_df["error"] = eval_df["y_pred"] - eval_df["y_true"]

    overall_rmse = float(np.sqrt(mean_squared_error(y_true_arr, y_pred_arr)))
    overall_mae = float(mean_absolute_error(y_true_arr, y_pred_arr))

    report: dict[str, Any] = {
        "overall": {
            "total_students": int(eval_df["student_id"].nunique()) if "student_id" in eval_df.columns else len(eval_df),
            "total_samples": len(eval_df),
            "rmse": round(overall_rmse, 3),
            "mae": round(overall_mae, 3),
            "pass_mark_threshold": pass_mark,
        },
        "attributes": {},
    }

    # Evaluate protected attributes: gender and category
    for attr in ["gender", "category"]:
        if attr not in eval_df.columns:
            continue

        report["attributes"][attr] = {}
        grouped = eval_df.groupby(attr, dropna=False)

        for group_val, group_data in grouped:
            group_name = str(group_val) if pd.notna(group_val) else "Unrecorded"
            n_students = int(group_data["student_id"].nunique()) if "student_id" in group_data.columns else len(group_data)
            n_samples = len(group_data)

            # Suppress small cohorts to prevent re-identification and noisy reporting
            if n_students < min_group_size:
                report["attributes"][attr][group_name] = {
                    "status": "suppressed",
                    "reason": f"Sample size too small ({n_students} students < {min_group_size})",
                    "student_count": n_students,
                    "sample_count": n_samples,
                }
                continue

            g_true = group_data["y_true"].values
            g_pred = group_data["y_pred"].values

            g_rmse = float(np.sqrt(mean_squared_error(g_true, g_pred)))
            g_mae = float(mean_absolute_error(g_true, g_pred))
            mean_error = float(np.mean(group_data["error"].values))

            # Disparity metrics at pass mark
            actual_pass = g_true >= pass_mark
            pred_pass = g_pred >= pass_mark
            actual_fail = ~actual_pass

            fn = int(np.sum(actual_pass & (~pred_pass))) # False alarm (predicted fail, actually passed)
            fp = int(np.sum(actual_fail & pred_pass))     # Missed risk (predicted pass, actually failed)

            false_negative_rate = float(fn / np.sum(actual_pass)) if np.sum(actual_pass) > 0 else 0.0
            false_positive_rate = float(fp / np.sum(actual_fail)) if np.sum(actual_fail) > 0 else 0.0

            report["attributes"][attr][group_name] = {
                "status": "reported",
                "student_count": n_students,
                "sample_count": n_samples,
                "rmse": round(g_rmse, 3),
                "mae": round(g_mae, 3),
                "mean_error": round(mean_error, 3),
                "rmse_disparity_to_overall": round(g_rmse - overall_rmse, 3),
                "false_alarm_rate": round(false_negative_rate, 4),
                "missed_risk_rate": round(false_positive_rate, 4),
            }

    return report


def save_fairness_report(
    report: dict[str, Any],
    report_filename: str = "fairness_audit_model_b.json",
    artifact_dir: Optional[Path | str] = None,
) -> Path:
    """
    Persists audit report exclusively to the offline model artifact directory.
    """
    if artifact_dir is not None:
        base_dir = Path(artifact_dir).resolve()
    else:
        import os
        model_env = os.environ.get("MODEL_ARTIFACT_DIR")
        if model_env:
            base_dir = Path(model_env).resolve()
        else:
            try:
                from django.conf import settings
                base_dir = Path(settings.MODEL_ARTIFACT_DIR).resolve()
            except Exception:
                base_dir = Path(__file__).resolve().parent.parent.parent / "artifacts" / "models"

    base_dir.mkdir(parents=True, exist_ok=True)

    target_path = base_dir / report_filename
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return target_path
