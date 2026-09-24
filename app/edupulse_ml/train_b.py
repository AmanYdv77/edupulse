"""
Training and candidate selection pipeline for Model B (Institute Custom Model).
Implements grouped cross-validation, strictly isolated temporal holdout evaluation,
and anti-leakage guards across institutional student cohorts.
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from edupulse_ml.contract import validate_feature_list
from edupulse_ml.evaluate import evaluate_regression
from edupulse_ml.fairness import audit_demographic_fairness, save_fairness_report


class NaiveBaselineRegressor(BaseEstimator, RegressorMixin):
    """
    Baseline regressor that forecasts exam performance using a student's prior semester score.
    Falls back to global training mean if student has no prior history.
    """
    def __init__(self):
        self.global_mean_ = 50.0

    def fit(self, X: pd.DataFrame, y: np.ndarray):
        self.global_mean_ = float(np.mean(y)) if len(y) > 0 else 50.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if isinstance(X, pd.DataFrame) and "previous_score" in X.columns:
            preds = X["previous_score"].fillna(self.global_mean_).values
        else:
            preds = np.full(len(X), self.global_mean_)
        return np.clip(np.asarray(preds, dtype=float), 0.0, 100.0)


def get_feature_columns(df: pd.DataFrame, use_habits: bool = False) -> list[str]:
    """
    Identifies approved feature columns present in the dataset.
    """
    base_features = ["attendance_percentage", "previous_score", "internal_assessment_score"]
    habit_features = ["hours_studied", "sleep_hours", "tutoring_sessions", "physical_activity"]

    features = [f for f in base_features if f in df.columns]
    if use_habits:
        features += [f for f in habit_features if f in df.columns]

    validate_feature_list(features, model_kind="institute")
    return features


def split_temporal_holdout(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits dataset chronologically: holds out the latest semester as the test set,
    training exclusively on earlier semesters. Prevents temporal data leakage.
    """
    if "semester" not in df.columns:
        raise ValueError("Dataset must contain 'semester' column for temporal splitting.")

    semesters = sorted(df["semester"].unique())
    if len(semesters) < 2:
        raise ValueError(
            f"Need at least 2 distinct semesters for temporal holdout splitting, found {len(semesters)}."
        )

    latest_semester = semesters[-1]
    train_df = df[df["semester"] < latest_semester].copy().reset_index(drop=True)
    test_df = df[df["semester"] == latest_semester].copy().reset_index(drop=True)

    if train_df.empty or test_df.empty:
        raise ValueError(
            f"Invalid temporal split: train={len(train_df)} rows, test={len(test_df)} rows."
        )

    return train_df, test_df


def train_and_evaluate_model_b(
    df: pd.DataFrame,
    use_habits: bool = False,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Executes the end-to-end Model B training workflow:
    1. Temporal Holdout Split (train on earlier semesters, test on latest semester).
    2. Grouped K-Fold Cross Validation on train_df grouped by student_id.
    3. Evaluates 3 candidates: Naive Baseline, Ridge, and HistGradientBoostingRegressor.
    4. Selects candidate with lowest grouped-CV RMSE.
    5. Evaluates winning candidate on holdout test_df.
    6. Conducts audit-only demographic fairness analysis.
    7. Serializes candidate artifact to settings.MODEL_ARTIFACT_DIR.

    Returns:
        dict: Complete training run metrics, holdout scores, and artifact metadata.
    """
    feature_names = get_feature_columns(df, use_habits=use_habits)
    train_df, test_df = split_temporal_holdout(df)

    X_train = train_df[feature_names]
    y_train = train_df["target_percentage"].values
    groups_train = train_df["student_id"].values

    X_test = test_df[feature_names]
    y_test = test_df["target_percentage"].values

    # Define Candidate Estimators
    candidates = {
        "naive_baseline": NaiveBaselineRegressor(),
        "ridge": Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=10.0, random_state=random_state)),
        ]),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=60,
            max_leaf_nodes=15,
            min_samples_leaf=10,
            learning_rate=0.08,
            random_state=random_state,
        ),
    }

    # Grouped Cross-Validation (Grouping strictly by student_id to avoid leakage)
    n_groups = len(np.unique(groups_train))
    n_splits = min(5, n_groups)
    if n_splits < 2:
        raise ValueError(f"Insufficient distinct students ({n_groups}) for grouped cross-validation.")

    gkf = GroupKFold(n_splits=n_splits)
    cv_scores = {}

    for name, model in candidates.items():
        fold_rmses = []
        for train_idx, val_idx in gkf.split(X_train, y_train, groups=groups_train):
            X_tr, y_tr = X_train.iloc[train_idx], y_train[train_idx]
            X_val, y_val = X_train.iloc[val_idx], y_train[val_idx]

            m = copy.deepcopy(model)
            m.fit(X_tr, y_tr)

            preds = m.predict(X_val)
            fold_rmses.append(float(np.sqrt(np.mean((y_val - np.clip(preds, 0.0, 100.0)) ** 2))))

        cv_scores[name] = float(np.mean(fold_rmses))

    # Evaluate naive baseline directly on holdout test set
    naive_model = NaiveBaselineRegressor().fit(X_train, y_train)
    naive_test_preds = naive_model.predict(X_test)
    baseline_metrics = evaluate_regression(y_test, naive_test_preds)

    # Select best ML candidate between Ridge and HistGradientBoosting (excluding naive from artifact)
    ml_candidates = {k: v for k, v in cv_scores.items() if k != "naive_baseline"}
    best_candidate_name = min(ml_candidates, key=ml_candidates.get)
    best_pipeline = candidates[best_candidate_name]

    # Retrain winning candidate on entire train_df
    best_pipeline.fit(X_train, y_train)
    test_preds = best_pipeline.predict(X_test)
    candidate_metrics = evaluate_regression(y_test, test_preds)

    # Demographic Fairness Audit
    fairness_report = audit_demographic_fairness(
        y_true=y_test,
        y_pred=test_preds,
        metadata=test_df,
    )

    # Save artifact
    data_fingerprint = hashlib.sha256(train_df.to_json().encode("utf-8")).hexdigest()[:16]
    artifact_filename = f"institute_model_b_{best_candidate_name}_{data_fingerprint}.joblib"
    artifact_dir = Path(settings.MODEL_ARTIFACT_DIR).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_pipeline, artifact_dir / artifact_filename)

    # Save fairness report
    report_filename = f"fairness_audit_{artifact_filename}.json"
    save_fairness_report(fairness_report, report_filename)

    return {
        "candidate_name": best_candidate_name,
        "feature_names": feature_names,
        "artifact_file": artifact_filename,
        "data_fingerprint": data_fingerprint,
        "n_train_rows": len(train_df),
        "n_test_rows": len(test_df),
        "cv_scores": cv_scores,
        "candidate_metrics": candidate_metrics,
        "baseline_metrics": baseline_metrics,
        "fairness_report": fairness_report,
        "latest_holdout_semester": int(test_df["semester"].iloc[0]),
    }
