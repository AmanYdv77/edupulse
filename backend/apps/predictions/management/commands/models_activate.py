"""
Management command to activate a model version and deactivate existing active versions in that slot.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from predictions.models import ModelVersion
from predictions.services import PredictorService


class Command(BaseCommand):
    help = "Activates a model version by ID and deactivates any existing active version in the same slot."

    def add_arguments(self, parser):
        parser.add_argument("version_id", type=int, help="Database ID of the ModelVersion to activate")

    def handle(self, *args, **options):
        version_id = options["version_id"]

        try:
            target = ModelVersion.objects.get(pk=version_id)
        except ModelVersion.DoesNotExist:
            raise CommandError(f"ModelVersion with ID {version_id} does not exist.")

        with transaction.atomic():
            # Deactivate currently active models in the target slot
            ModelVersion.objects.filter(slot=target.slot, is_active=True).update(is_active=False)

            # Activate target model
            target.is_active = True
            target.save(update_fields=["is_active"])

        # Invalidate in-memory cache
        PredictorService.clear_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully activated {target.slot} v{target.version} (id={target.id}, file='{target.artifact_file}')."
            )
        )
