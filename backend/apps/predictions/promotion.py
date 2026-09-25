"""
Promotion criteria and validation rules for Model B (Institutional Custom Model).
Enforces empirical superiority over the naive baseline and incumbent Model A
before any custom model can be recommended for activation.
"""

from typing import Any, Mapping, Optional, Sequence, Tuple
from django.conf import settings


def should_promote(
    candidate_metrics: Mapping[str, Any],
    incumbent_metrics: Optional[Mapping[str, Any]],
    baseline_metrics: Mapping[str, Any],
    margin: Optional[float] = None,
) -> Tuple[bool, list[str]]:
    """
    Evaluates whether a newly trained Model B candidate qualifies to replace the incumbent model.

    Promotion Rules (from docs/ML_CONTRACT.md):
    1. Candidate must achieve lower RMSE than the naive prior-semester baseline.
    2. An incumbent model (Model A) must exist and be evaluatable on the same holdout dataset.
    3. Candidate must beat Model A by at least `margin` RMSE points (default: 2.0).

    Parameters:
        candidate_metrics: Dict containing at least 'rmse' for the candidate model on holdout.
        incumbent_metrics: Dict containing at least 'rmse' for Model A on holdout, or None.
        baseline_metrics: Dict containing at least 'rmse' for the naive baseline on holdout.
        margin: Minimum required RMSE improvement over incumbent (defaults to settings.MODEL_B_PROMOTION_MARGIN_RMSE).

    Returns:
        Tuple[bool, list[str]]: (is_promotable, list of explanatory reasons).
    """
    if margin is None:
        margin = getattr(settings, "MODEL_B_PROMOTION_MARGIN_RMSE", 2.0)

    candidate_rmse = float(candidate_metrics.get("rmse", float("inf")))
    baseline_rmse = float(baseline_metrics.get("rmse", float("inf")))

    reasons: list[str] = []
    is_promoted = True

    # Rule 1: Must beat naive baseline
    if candidate_rmse >= baseline_rmse:
        is_promoted = False
        reasons.append(
            f"Candidate RMSE ({candidate_rmse:.2f}) failed to beat the naive baseline RMSE ({baseline_rmse:.2f})."
        )
    else:
        reasons.append(
            f"Candidate beat naive baseline: RMSE {candidate_rmse:.2f} vs {baseline_rmse:.2f} "
            f"(+{baseline_rmse - candidate_rmse:.2f} points)."
        )

    # Rule 2: Incumbent comparison
    if incumbent_metrics is None or "rmse" not in incumbent_metrics:
        is_promoted = False
        reasons.append(
            "Incumbent Model A metrics unavailable on holdout evaluation set. "
            "Promotion requires direct empirical comparison."
        )
        return is_promoted, reasons

    incumbent_rmse = float(incumbent_metrics["rmse"])
    improvement = incumbent_rmse - candidate_rmse

    # Rule 3: Must beat incumbent by margin
    if improvement < margin:
        is_promoted = False
        reasons.append(
            f"Candidate RMSE ({candidate_rmse:.2f}) did not beat incumbent Model A ({incumbent_rmse:.2f}) "
            f"by the required margin of {margin:.1f} RMSE points. (Improvement: {improvement:+.2f})."
        )
    else:
        reasons.append(
            f"Candidate beat incumbent Model A by {improvement:.2f} points, "
            f"satisfying the required margin of {margin:.1f} RMSE points."
        )

    return is_promoted, reasons
