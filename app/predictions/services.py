"""
Service layer for loading machine learning models and generating score predictions.
Enforces artifact path sandboxing, runtime library compatibility, and strict data validation.
"""

import logging
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import joblib
import pandas as pd
import sklearn
from django.conf import settings
from edupulse_ml.contract import validate_feature_list, validate_row
from .models import ModelVersion

logger = logging.getLogger(__name__)


class IncompatibleEnvironmentError(Exception):
    """Raised when the serialized model artifact was built with an incompatible library version."""
    pass


class ModelNotFoundError(Exception):
    """Raised when no active ModelVersion is registered for the requested slot."""
    pass


def resolve_artifact_path(artifact_file: str) -> Path:
    """
    Resolves artifact_file strictly inside settings.MODEL_ARTIFACT_DIR.
    Rejects any path separators ('/', '\\') or directory traversal ('..').

    SECURITY WARNING:
    joblib and pickle files deserialize Python objects by executing arbitrary code.
    Model artifact files must NEVER be retrieved or loaded from untrusted,
    unauthenticated, or user-supplied external sources.
    """
    if not artifact_file or not isinstance(artifact_file, str):
        raise ValueError("artifact_file must be a non-empty string.")

    if "/" in artifact_file or "\\" in artifact_file or ".." in artifact_file:
        raise ValueError(
            f"Path escape attempt detected: '{artifact_file}' contains invalid directory navigation."
        )

    base_dir = Path(settings.MODEL_ARTIFACT_DIR).resolve()
    resolved = (base_dir / artifact_file).resolve()

    if resolved.parent != base_dir:
        raise ValueError(
            f"Artifact path '{resolved}' escapes the configured artifact directory '{base_dir}'."
        )

    return resolved


class PredictorService:
    """
    Inference service managing cached model lifecycles and strictly validated predictions.
    """

    _cache: dict[int, Any] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory loaded model cache."""
        cls._cache.clear()

    @classmethod
    def get_active_model_version(cls, slot: str) -> Optional[ModelVersion]:
        """Returns the currently active ModelVersion for the given slot, or None."""
        return ModelVersion.objects.filter(slot=slot, is_active=True).first()

    @classmethod
    def load(cls, slot: str) -> Any:
        """
        Loads and returns the active model for the given slot.
        Verifies scikit-learn version compatibility, validates feature contract,
        and resolves the artifact path inside the secure artifact directory.
        Caches the model instance per process keyed by ModelVersion id.
        """
        model_version = cls.get_active_model_version(slot)
        if not model_version:
            raise ModelNotFoundError(f"No active model found for slot '{slot}'.")

        if model_version.id in cls._cache:
            return cls._cache[model_version.id]

        # 1. Compatibility check: refuse mismatched scikit-learn version
        current_sklearn = sklearn.__version__
        if model_version.sklearn_version != current_sklearn:
            err_msg = (
                f"ModelVersion id={model_version.id} ({model_version.slot} v{model_version.version}) "
                f"was trained with scikit-learn '{model_version.sklearn_version}', but current runtime "
                f"is '{current_sklearn}'. Refusing to load incompatible model."
            )
            logger.error(err_msg)
            raise IncompatibleEnvironmentError(err_msg)

        # 2. ML Contract validation: verify features adhere to governance
        validate_feature_list(model_version.feature_names, model_kind=slot)

        # 3. Path resolution & safety
        artifact_path = resolve_artifact_path(model_version.artifact_file)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact file not found at '{artifact_path}'.")

        # 4. Load artifact and cache
        loaded_model = joblib.load(artifact_path)
        cls._cache[model_version.id] = loaded_model
        return loaded_model

    @classmethod
    def predict(cls, slot: str, rows: Sequence[Mapping[str, Any]]) -> list[dict]:
        """
        Generates score forecasts for a collection of sample rows.
        Validates every row with validate_row; NEVER invents or substitutes default numbers.
        Returns per-row results with predicted percentage or an 'insufficient_data' reason.
        """
        model_version = cls.get_active_model_version(slot)
        if not model_version:
            raise ModelNotFoundError(f"No active model found for slot '{slot}'.")

        model = cls.load(slot)
        feature_names = model_version.feature_names
        results = []

        for row in rows:
            problems = validate_row(row)

            # Check that every expected feature exists in the input row
            missing_features = [f for f in feature_names if f not in row or row[f] is None]
            if missing_features:
                problems.append(f"Missing required features: {missing_features}")

            if problems:
                results.append({
                    "status": "insufficient_data",
                    "problems": problems,
                })
                continue

            # Construct DataFrame matching exact feature column order
            input_df = pd.DataFrame([{f: row[f] for f in feature_names}])
            raw_prediction = model.predict(input_df)[0]
            score = max(0.0, min(100.0, float(raw_prediction)))

            results.append({
                "status": "success",
                "predicted_percentage": round(score, 1),
                "is_at_risk": score < 40.0,
            })

        return results
