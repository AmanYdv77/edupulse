"""
Model registry database models for EduPulse.
Tracks trained model versions, evaluation metrics, compatibility metadata, and active status.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ModelVersion(models.Model):
    """
    Registry entry for a trained machine learning model.
    Models can occupy either the 'baseline' (Model A) or 'institute' (Model B) slot.
    At most one model version may be active per slot at any given time.
    """

    SLOT_BASELINE = "baseline"
    SLOT_INSTITUTE = "institute"
    SLOT_CHOICES = [
        (SLOT_BASELINE, "Baseline (Model A)"),
        (SLOT_INSTITUTE, "Institute (Model B)"),
    ]

    slot = models.CharField(
        max_length=20,
        choices=SLOT_CHOICES,
        db_index=True,
        help_text="Deployment slot ('baseline' or 'institute')",
    )
    version = models.PositiveIntegerField(
        help_text="Sequential version integer within the slot",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this version was registered",
    )
    trained_on = models.CharField(
        max_length=255,
        help_text="Short description of dataset/cohort used for training",
    )
    n_train_rows = models.PositiveIntegerField(
        help_text="Number of samples in training split",
    )
    n_test_rows = models.PositiveIntegerField(
        help_text="Number of samples in evaluation/holdout split",
    )
    metrics = models.JSONField(
        default=dict,
        help_text="Evaluation metrics dictionary (e.g. {'rmse': 4.12, 'r2': 0.74})",
    )
    feature_names = models.JSONField(
        default=list,
        help_text="List of input feature names in exact column order",
    )
    sklearn_version = models.CharField(
        max_length=32,
        help_text="scikit-learn package version at training time",
    )
    python_version = models.CharField(
        max_length=32,
        help_text="Python runtime version at training time",
    )
    data_fingerprint = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of training dataset frame",
    )
    artifact_file = models.CharField(
        max_length=255,
        help_text="Filename of serialized joblib model (must reside in MODEL_ARTIFACT_DIR)",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Designates whether this version actively serves predictions for its slot",
    )

    class Meta:
        ordering = ["slot", "-version"]
        verbose_name = "Model Version"
        verbose_name_plural = "Model Versions"
        constraints = [
            models.UniqueConstraint(
                fields=["slot", "version"],
                name="unique_version_per_slot",
            ),
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(is_active=True),
                name="unique_active_model_per_slot",
            ),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "inactive"
        return f"{self.slot} v{self.version} [{status}] ({self.artifact_file})"


class PredictionSnapshot(models.Model):
    """
    Immutable historical audit snapshot of a model inference result.
    Captures input features, model version, predicted score, risk band, and reasoning.
    Snapshots are created in batch and NEVER modified after insertion.
    """

    student = models.ForeignKey(
        "academics.StudentProfile",
        on_delete=models.CASCADE,
        related_name="prediction_snapshots",
        help_text="Student for whom inference was conducted",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        related_name="prediction_snapshots",
        help_text="Academic subject evaluated",
    )
    semester = models.IntegerField(
        help_text="Semester number at prediction time",
    )
    taken_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp when this prediction snapshot was generated",
    )
    checkpoint = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Administrative checkpoint (e.g. 'live', 'midterm', 'pre-exam')",
    )
    model_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.CASCADE,
        related_name="snapshots",
        help_text="ModelVersion artifact used to execute inference",
    )
    features = models.JSONField(
        default=dict,
        help_text="Exact feature vector dictionary provided to the model",
    )
    predicted_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted marks percentage (0.0 - 100.0), or None if telemetry was insufficient",
    )
    risk_band = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low Risk"),
            ("medium", "Medium Risk"),
            ("high", "High Risk"),
            ("insufficient_data", "Insufficient Data"),
        ],
        help_text="Categorical risk classification based on pass mark threshold and data completeness",
    )
    reasons = models.JSONField(
        default=list,
        help_text="Explanatory factors, missing feature warnings, or key drivers",
    )

    class Meta:
        ordering = ["-taken_at", "-id"]
        verbose_name = "Prediction Snapshot"
        verbose_name_plural = "Prediction Snapshots"
        indexes = [
            models.Index(fields=["student", "semester", "taken_at"], name="idx_pred_snap_student_sem_time"),
            models.Index(fields=["model_version", "taken_at"], name="idx_pred_snap_model_time"),
            models.Index(fields=["checkpoint", "taken_at"], name="idx_pred_snap_checkpoint_time"),
        ]

    @property
    def is_at_risk(self) -> bool:
        """Convenience property for views and templates."""
        return self.risk_band in ("high", "insufficient_data")

    def save(self, *args, **kwargs):
        if self.pk is not None and PredictionSnapshot.objects.filter(pk=self.pk).exists():
            raise ValidationError("PredictionSnapshot records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def __str__(self):
        score_repr = f"{self.predicted_percentage}%" if self.predicted_percentage is not None else "N/A"
        return f"Snapshot {self.student.roll_no} | {self.subject.code} | {self.risk_band} ({score_repr}) @ {self.checkpoint}"
