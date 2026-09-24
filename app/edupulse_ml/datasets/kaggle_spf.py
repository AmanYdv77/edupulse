"""
Dataset loader for the Kaggle Student Performance Factors (SPF) benchmark dataset.
Enforces ML contract naming, strips protected/unapproved attributes, and filters invalid rows.
NEVER reads from the application database.
"""

import hashlib
import logging
from pathlib import Path
from typing import Tuple
import pandas as pd
from edupulse_ml.contract import FEATURES, validate_feature_list

logger = logging.getLogger(__name__)

# Column mapping from Kaggle CSV headers to approved contract feature names
COLUMN_MAPPING = {
    "Hours_Studied": "hours_studied",
    "Attendance": "attendance_percentage",
    "Sleep_Hours": "sleep_hours",
    "Previous_Scores": "previous_score",
    "Tutoring_Sessions": "tutoring_sessions",
    "Physical_Activity": "physical_activity",
}

TARGET_COLUMN = "Exam_Score"

# Explicit audit documentation of dropped attributes
DROPPED_COLUMNS_REASONS = {
    "Gender": "Protected demographic characteristic (strictly banned by ML contract)",
    "Learning_Disabilities": "Protected health/accommodation characteristic (strictly banned by ML contract)",
    "Family_Income": "Unapproved socio-economic proxy variable",
    "Parental_Education_Level": "Unapproved socio-economic background proxy",
    "Distance_from_Home": "Unapproved commuting proxy; non-actionable as academic predictor",
    "Internet_Access": "Unapproved infrastructure proxy variable",
    "Access_to_Resources": "Unapproved subjective survey metric",
    "Parental_Involvement": "Unapproved subjective survey metric",
    "Motivation_Level": "Unapproved subjective survey metric",
    "Teacher_Quality": "External institutional attribute not collected per-student",
    "School_Type": "External institutional attribute not collected per-student",
    "Peer_Influence": "Unapproved subjective survey metric",
    "Extracurricular_Activities": "Unapproved non-academic activity proxy",
}


def load_kaggle_spf(csv_path: Path) -> Tuple[pd.DataFrame, pd.Series, dict]:
    """
    Loads and cleans the Kaggle Student Performance Factors dataset from the given CSV path.

    Returns:
        X (pd.DataFrame): Cleaned feature matrix containing ONLY approved baseline features.
        y (pd.Series): Target examination score series (0.0 to 100.0).
        metadata (dict): Processing metadata including drop counts, fingerprint, and dropped columns audit.
    """
    csv_file = Path(csv_path)
    if not csv_file.is_file():
        raise FileNotFoundError(f"Kaggle SPF CSV file not found at '{csv_file}'.")

    raw_df = pd.read_csv(csv_file)
    initial_rows = len(raw_df)

    if TARGET_COLUMN not in raw_df.columns:
        raise ValueError(f"Required target column '{TARGET_COLUMN}' missing from CSV.")

    # 1. Filter out-of-bounds target scores (must be between 0.0 and 100.0)
    valid_mask = (raw_df[TARGET_COLUMN] >= 0.0) & (raw_df[TARGET_COLUMN] <= 100.0)
    dropped_oob_scores = int((~valid_mask).sum())
    df = raw_df[valid_mask].copy()

    # 2. Rename approved feature columns to contract names
    df = df.rename(columns=COLUMN_MAPPING)

    # 3. Restrict strictly to contract-approved baseline features
    approved_baseline_features = [
        name for name, spec in FEATURES.items()
        if "baseline" in spec.allowed_models
    ]
    # Validate against contract
    validate_feature_list(approved_baseline_features, model_kind="baseline")

    # Ensure all approved features are present
    missing_in_csv = [f for f in approved_baseline_features if f not in df.columns]
    if missing_in_csv:
        raise ValueError(f"CSV is missing required contract features: {missing_in_csv}")

    # Drop any remaining rows with missing values in approved features or target
    before_na_drop = len(df)
    df = df.dropna(subset=approved_baseline_features + [TARGET_COLUMN]).copy()
    dropped_na = before_na_drop - len(df)

    X = df[approved_baseline_features].copy()
    y = df[TARGET_COLUMN].astype(float).copy()

    # 4. Generate SHA-256 fingerprint of the cleaned feature dataset
    dataset_bytes = pd.concat([X, y], axis=1).to_csv(index=False).encode("utf-8")
    data_fingerprint = hashlib.sha256(dataset_bytes).hexdigest()

    metadata = {
        "initial_rows": initial_rows,
        "valid_rows": len(df),
        "dropped_oob_scores": dropped_oob_scores,
        "dropped_na_rows": dropped_na,
        "feature_names": approved_baseline_features,
        "dropped_columns": DROPPED_COLUMNS_REASONS,
        "data_fingerprint": data_fingerprint,
    }

    logger.info(
        f"Loaded Kaggle SPF dataset: {len(df)} valid rows (dropped {dropped_oob_scores} out-of-bounds, "
        f"{dropped_na} nulls). Data fingerprint: {data_fingerprint[:16]}..."
    )

    return X, y, metadata
