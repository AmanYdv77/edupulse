"""
Evaluation metrics for EduPulse predictive modeling.
Computes continuous regression statistics and threshold-based academic pass/fail classification metrics.
"""

from typing import Any, Mapping
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def evaluate_regression(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    pass_mark: float = 40.0,
) -> dict[str, Any]:
    """
    Computes regression error metrics and confusion matrix at the given pass mark threshold.

    Parameters:
        y_true: Actual exam percentage scores (0-100).
        y_pred: Predicted exam percentage scores (0-100).
        pass_mark: Minimum passing percentage (default 40.0, from ML contract).

    Returns:
        dict: Summary metrics including rmse, mae, r2, and classification confusion matrix.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)

    # Bound predictions to [0.0, 100.0]
    y_pred_bounded = np.clip(y_pred_arr, 0.0, 100.0)

    # Regression statistics
    rmse = float(np.sqrt(mean_squared_error(y_true_arr, y_pred_bounded)))
    mae = float(mean_absolute_error(y_true_arr, y_pred_bounded))
    r2 = float(r2_score(y_true_arr, y_pred_bounded))

    # Pass/fail classification evaluation at pass_mark
    actual_pass = y_true_arr >= pass_mark
    pred_pass = y_pred_bounded >= pass_mark

    tp = int(np.sum(actual_pass & pred_pass))       # Correctly predicted pass
    tn = int(np.sum((~actual_pass) & (~pred_pass))) # Correctly predicted fail (at-risk)
    fp = int(np.sum((~actual_pass) & pred_pass))     # Missed risk (predicted pass, actually failed)
    fn = int(np.sum(actual_pass & (~pred_pass)))     # False alarm (predicted fail, actually passed)

    total = len(y_true_arr)
    acc = float((tp + tn) / total) if total > 0 else 0.0

    return {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "r2": round(r2, 4),
        "pass_mark_threshold": pass_mark,
        "confusion_matrix": {
            "true_pass": tp,
            "true_fail": tn,
            "false_pass": fp,
            "false_fail": fn,
            "classification_accuracy": round(acc, 4),
        },
    }
