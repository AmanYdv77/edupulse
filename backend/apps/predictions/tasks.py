"""
Celery background tasks for EduPulse Predictions Domain.
"""

import logging
from typing import Any, Dict, Optional
from celery import shared_task

from academics.models import StudentProfile
from predictions.models import PredictionSnapshot
from predictions.services import PredictorService, predict_for_students

logger = logging.getLogger(__name__)


@shared_task(
    name="predictions.take_snapshots",
    bind=True,
    acks_late=True,
    soft_time_limit=300,
    time_limit=330,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def take_prediction_snapshots(
    self, checkpoint: Optional[str] = None, slot: str = "baseline"
) -> Dict[str, Any]:
    """
    Periodic task to compute batch predictions and store immutable PredictionSnapshots.
    Idempotent: skips existing snapshots for the specified checkpoint.
    Zero PII is accepted or logged.
    """
    cp_name = (checkpoint or "weekly").strip()
    task_id = getattr(getattr(self, "request", None), "id", "local")
    logger.info(
        "Starting task predictions.take_snapshots [id=%s, checkpoint=%s, slot=%s]",
        task_id,
        cp_name,
        slot,
    )

    active_model = PredictorService.get_active_model_version(slot)
    if not active_model:
        logger.warning(
            "predictions.take_snapshots skipped: no active model version found for slot '%s'",
            slot,
        )
        return {
            "status": "skipped",
            "reason": f"No active ModelVersion for slot '{slot}'",
            "checkpoint": cp_name,
            "created_count": 0,
            "skipped_count": 0,
        }

    students = list(
        StudentProfile.objects.filter(user__is_active=True).select_related("course", "user")
    )
    if not students:
        logger.info("predictions.take_snapshots: 0 active students found.")
        return {
            "status": "success",
            "checkpoint": cp_name,
            "total_students": 0,
            "created_count": 0,
            "skipped_count": 0,
        }

    results = predict_for_students(students, model_version=active_model, slot=slot)

    existing_keys = set(
        PredictionSnapshot.objects.filter(checkpoint=cp_name).values_list(
            "student_id", "subject_id", "semester"
        )
    )

    snapshots_to_create = []
    skipped_count = 0

    for r in results:
        key = (r.student_id, r.subject_id, r.semester)
        if key in existing_keys:
            skipped_count += 1
            continue

        snapshots_to_create.append(
            PredictionSnapshot(
                student_id=r.student_id,
                subject_id=r.subject_id,
                semester=r.semester,
                checkpoint=cp_name,
                model_version=active_model,
                features=r.features,
                predicted_percentage=r.predicted_percentage,
                risk_band=r.risk_band,
                reasons=r.reasons,
            )
        )

    if snapshots_to_create:
        PredictionSnapshot.objects.bulk_create(snapshots_to_create)

    created_count = len(snapshots_to_create)
    logger.info(
        "Finished predictions.take_snapshots [id=%s]: %d snapshots created, %d skipped across %d students.",
        task_id,
        created_count,
        skipped_count,
        len(students),
    )

    return {
        "status": "success",
        "checkpoint": cp_name,
        "total_students": len(students),
        "created_count": created_count,
        "skipped_count": skipped_count,
    }
