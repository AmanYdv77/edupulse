"""
Model registry database models for EduPulse.
Tracks trained model versions, evaluation metrics, compatibility metadata, and active status.
"""

from django.db import models
from django.db.models import Q


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
