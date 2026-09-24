"""
Management command to list all registered machine learning model versions.
"""

from django.core.management.base import BaseCommand
from predictions.models import ModelVersion


class Command(BaseCommand):
    help = "Lists all registered machine learning model versions and their active statuses."

    def handle(self, *args, **options):
        models = ModelVersion.objects.all().order_by("slot", "version")

        if not models.exists():
            self.stdout.write(self.style.WARNING("No registered model versions found."))
            return

        header = f"{'ID':<5} | {'Slot':<12} | {'Ver':<5} | {'Active':<8} | {'Sklearn':<10} | {'Trained On':<25} | {'Metrics'}"
        separator = "-" * len(header)

        self.stdout.write(separator)
        self.stdout.write(header)
        self.stdout.write(separator)

        for m in models:
            active_str = "YES" if m.is_active else "no"
            metrics_str = ", ".join(f"{k}={v}" for k, v in m.metrics.items()) if m.metrics else "None"
            row = (
                f"{m.id:<5} | {m.slot:<12} | v{m.version:<4} | {active_str:<8} | "
                f"{m.sklearn_version:<10} | {m.trained_on[:23]:<25} | {metrics_str}"
            )
            if m.is_active:
                self.stdout.write(self.style.SUCCESS(row))
            else:
                self.stdout.write(row)

        self.stdout.write(separator)
