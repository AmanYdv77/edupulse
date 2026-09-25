"""
Training and model selection pipeline for Model A (Baseline).
Trains candidates on Kaggle SPF dataset using 5-fold CV on the training split,
selects the top candidate by CV RMSE, evaluates once on the holdout test set,
and serializes the winning pipeline.
"""

import json
import logging
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from edupulse_ml.datasets.kaggle_spf import load_kaggle_spf
from edupulse_ml.evaluate import evaluate_regression

logger = logging.getLogger(__name__)

PASS_MARK_PERCENT = 40.0


def train_baseline_pipeline(
    csv_path: Path,
    artifact_dir: Path,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Executes the complete baseline training, model selection, evaluation, and serialization workflow.

    Parameters:
        csv_path: Path to the raw StudentPerformanceFactors.csv.
        artifact_dir: Directory where the serialized joblib artifact and metrics.json are written.
        random_state: Fixed random seed for split and model reproducibility (default 42).

    Returns:
        dict: Summary containing metadata, chosen candidate, evaluation metrics, and file paths.
    """
    artifact_path_dir = Path(artifact_dir)
    artifact_path_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ingest and sanitize data strictly according to ML contract
    X, y, meta = load_kaggle_spf(csv_path)

    # 2. Strict 80/20 train/test holdout split
    n_samples = len(X)
    indices = np.arange(n_samples)
    np.random.seed(random_state)
    np.random.shuffle(indices)

    split_idx = int(n_samples * 0.8)
    train_idx, test_idx = indices[:split_idx], indices[split_idx:]

    X_train, y_train = X.iloc[train_idx].copy(), y.iloc[train_idx].copy()
    X_test, y_test = X.iloc[test_idx].copy(), y.iloc[test_idx].copy()

    # 3. Define candidate model pipelines
    candidates = {}

    # Candidate 0: Naive baseline benchmark
    candidates["dummy_mean"] = DummyRegressor(strategy="mean")

    # Candidate family 1: Ridge regression with StandardScaler
    for alpha in [0.01, 0.1, 1.0, 10.0, 100.0]:
        candidates[f"ridge_alpha_{alpha}"] = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=alpha, random_state=random_state)),
        ])

    # Candidate family 2: HistGradientBoostingRegressor
    for max_iter in [50, 100]:
        for max_depth in [3, 5]:
            candidates[f"hgb_iter_{max_iter}_depth_{max_depth}"] = Pipeline([
                ("regressor", HistGradientBoostingRegressor(
                    max_iter=max_iter,
                    max_depth=max_depth,
                    random_state=random_state,
                )),
            ])

    # 4. 5-Fold cross-validation on TRAIN split only (never touching the test split)
    cv = KFold(n_splits=5, shuffle=True, random_state=random_state)
    cv_results = {}

    for name, estimator in candidates.items():
        # neg_root_mean_squared_error returns negative RMSE, so negate it
        scores = -cross_val_score(
            estimator, X_train, y_train,
            scoring="neg_root_mean_squared_error",
            cv=cv,
        )
        mean_cv_rmse = float(np.mean(scores))
        std_cv_rmse = float(np.std(scores))
        cv_results[name] = {
            "mean_cv_rmse": round(mean_cv_rmse, 4),
            "std_cv_rmse": round(std_cv_rmse, 4),
        }
        logger.info(f"CV evaluation for {name}: RMSE = {mean_cv_rmse:.4f} (+/- {std_cv_rmse:.4f})")

    # 5. Select best non-dummy model by lowest CV RMSE
    non_dummy_candidates = {k: v for k, v in cv_results.items() if k != "dummy_mean"}
    best_candidate_name = min(non_dummy_candidates, key=lambda k: non_dummy_candidates[k]["mean_cv_rmse"])
    best_estimator = candidates[best_candidate_name]

    # 6. Fit best estimator and dummy baseline on full training set
    best_estimator.fit(X_train, y_train)
    dummy_model = candidates["dummy_mean"]
    dummy_model.fit(X_train, y_train)

    # 7. Evaluate on the untouched holdout test set (only once)
    y_test_pred_best = best_estimator.predict(X_test)
    y_test_pred_dummy = dummy_model.predict(X_test)

    test_metrics = evaluate_regression(y_test, y_test_pred_best, pass_mark=PASS_MARK_PERCENT)
    dummy_metrics = evaluate_regression(y_test, y_test_pred_dummy, pass_mark=PASS_MARK_PERCENT)

    # 8. Save artifact into MODEL_ARTIFACT_DIR
    artifact_filename = "model_a_baseline.joblib"
    artifact_filepath = artifact_path_dir / artifact_filename
    joblib.dump(best_estimator, artifact_filepath)

    # 9. Save metrics.json alongside the artifact
    summary_metrics = {
        "slot": "baseline",
        "dataset": "Kaggle Student Performance Factors",
        "n_train_rows": len(X_train),
        "n_test_rows": len(X_test),
        "chosen_model": best_candidate_name,
        "cv_rmse": cv_results[best_candidate_name]["mean_cv_rmse"],
        "test_metrics": test_metrics,
        "dummy_metrics": dummy_metrics,
        "improvement_over_dummy_rmse": round(dummy_metrics["rmse"] - test_metrics["rmse"], 4),
        "feature_names": meta["feature_names"],
        "data_fingerprint": meta["data_fingerprint"],
        "artifact_file": artifact_filename,
    }

    metrics_json_path = artifact_path_dir / "metrics.json"
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=2)

    return summary_metrics
