"""
Management command: register_baseline_model

Idempotently registers and activates the bundled Model A baseline artifact
in the database on production/staging deployments.
"""

import json
import platform
from pathlib import Path
from typing import Any

import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from predictions.models import ModelVersion
from predictions.services import PredictorService


class Command(BaseCommand):
    help = "Idempotently registers and activates the bundled Model A baseline artifact."

    def handle(self, *args: Any, **options: Any) -> None:
        if not getattr(settings, "MODEL_ARTIFACT_DIR", None):
            raise CommandError("MODEL_ARTIFACT_DIR is not configured in settings.")

        artifact_dir = Path(settings.MODEL_ARTIFACT_DIR)
        metrics_path = artifact_dir / "metrics.json"
        model_file = artifact_dir / "model_a_baseline.joblib"

        if not model_file.is_file():
            self.stdout.write(
                self.style.WARNING(f"Model artifact not found at {model_file}; skipping baseline registration.")
            )
            return

        if not metrics_path.is_file():
            self.stdout.write(
                self.style.WARNING(f"Model metrics not found at {metrics_path}; skipping baseline registration.")
            )
            return

        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

        active_baseline = ModelVersion.objects.filter(slot="baseline", is_active=True).first()
        if active_baseline:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Baseline ModelVersion already active (ID={active_baseline.id}, v{active_baseline.version})."
                )
            )
            return

        mv, created = ModelVersion.objects.get_or_create(
            slot="baseline",
            version=1,
            defaults={
                "trained_on": metrics_data.get("dataset", "Kaggle Student Performance Factors (public sample data)"),
                "n_train_rows": metrics_data.get("n_train_rows", 5284),
                "n_test_rows": metrics_data.get("n_test_rows", 1322),
                "metrics": metrics_data,
                "feature_names": metrics_data.get("feature_names", []),
                "sklearn_version": sklearn.__version__,
                "python_version": platform.python_version(),
                "data_fingerprint": metrics_data.get("data_fingerprint", ""),
                "artifact_file": metrics_data.get("artifact_file", "model_a_baseline.joblib"),
                "is_active": True,
            },
        )

        if not mv.is_active:
            mv.is_active = True
            mv.save(update_fields=["is_active"])

        PredictorService.clear_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully registered and activated Model A baseline (ID={mv.id}, v{mv.version})."
            )
        )
