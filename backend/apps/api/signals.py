"""
Django signal handlers for event-driven cache invalidation across EduPulse.

Ensures real-time cache consistency for analytics and student predictions
without requiring explicit manual invalidation in every view or task.
"""

import logging
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from academics.models import (
    HabitCheckInLog,
    Result,
    SemesterResult,
    StudentHabitPreference,
)
from predictions.models import ModelVersion, PredictionSnapshot

from .caching import (
    invalidate_analytics_cache,
    invalidate_model_cache,
    invalidate_student_prediction_cache,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Result)
@receiver(post_delete, sender=Result)
def handle_result_change(sender, instance, **kwargs):
    """Invalidate analytics and student prediction caches when marks change."""
    invalidate_analytics_cache()
    if instance.student_id:
        invalidate_student_prediction_cache(instance.student_id)


@receiver(post_save, sender=SemesterResult)
@receiver(post_delete, sender=SemesterResult)
def handle_semester_result_change(sender, instance, **kwargs):
    """Invalidate analytics and student predictions when semester results change or are published."""
    invalidate_analytics_cache()
    if instance.student_id:
        invalidate_student_prediction_cache(instance.student_id)


@receiver(post_save, sender=PredictionSnapshot)
@receiver(post_delete, sender=PredictionSnapshot)
def handle_prediction_snapshot_change(sender, instance, **kwargs):
    """Invalidate analytics cache when new prediction snapshots are stored."""
    invalidate_analytics_cache()
    if instance.student_id:
        invalidate_student_prediction_cache(instance.student_id)


@receiver(post_save, sender=HabitCheckInLog)
@receiver(post_delete, sender=HabitCheckInLog)
def handle_habit_log_change(sender, instance, **kwargs):
    """Invalidate student prediction cache when student check-in log is created."""
    if instance.student_id:
        invalidate_student_prediction_cache(instance.student_id)


@receiver(post_save, sender=StudentHabitPreference)
@receiver(post_delete, sender=StudentHabitPreference)
def handle_habit_pref_change(sender, instance, **kwargs):
    """Invalidate student prediction cache when student habit preference changes."""
    if instance.student_id:
        invalidate_student_prediction_cache(instance.student_id)


@receiver(post_save, sender=ModelVersion)
@receiver(post_delete, sender=ModelVersion)
def handle_model_version_change(sender, instance, **kwargs):
    """Invalidate model registry and dependent caches when model status changes."""
    invalidate_model_cache()
