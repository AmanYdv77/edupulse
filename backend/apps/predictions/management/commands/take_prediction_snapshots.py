"""
Management command to execute batch inference and persist immutable PredictionSnapshots.
Usage:
    python manage.py take_prediction_snapshots --checkpoint <name>

Requirements:
1. Refuses to run if no active machine learning model is registered.
2. Evaluates all active students in batch using predict_for_students.
3. Safe to re-run: skips existing snapshots for the given checkpoint.
"""

from django.core.management.base import BaseCommand, CommandError
from academics.models import StudentProfile
from predictions.models import PredictionSnapshot
from predictions.services import PredictorService, predict_for_students


class Command(BaseCommand):
    help = "Generates and saves immutable prediction snapshots for all active students."

    def add_arguments(self, parser):
        parser.add_argument(
            "--checkpoint",
            type=str,
            required=True,
            help="Checkpoint name tag for this snapshot run (e.g. 'midterm', 'pre-exam', 'endterm')",
        )
        parser.add_argument(
            "--slot",
            type=str,
            default="baseline",
            help="Model registry slot to use ('baseline' or 'institute'). Default: 'baseline'",
        )

    def handle(self, *args, **options):
        checkpoint = options["checkpoint"].strip()
        slot = options["slot"].strip()

        if not checkpoint:
            raise CommandError("Checkpoint name cannot be empty.")

        # 1. Refuse execution without an active model
        active_model = PredictorService.get_active_model_version(slot)
        if not active_model:
            raise CommandError(
                f"No active ModelVersion registered for slot '{slot}'. "
                f"Activate a model with 'python manage.py models_activate <id>' before taking snapshots."
            )

        self.stdout.write(
            f"Taking prediction snapshots for checkpoint '{checkpoint}' using model {active_model.slot} v{active_model.version}..."
        )

        # 2. Fetch all active students
        students = list(
            StudentProfile.objects.filter(user__is_active=True).select_related("course", "user")
        )
        if not students:
            self.stdout.write(self.style.WARNING("No active students found."))
            return

        self.stdout.write(f"Executing batch inference across {len(students)} active student(s)...")

        # 3. True batch prediction
        results = predict_for_students(students, model_version=active_model, slot=slot)

        # 4. Check for existing snapshots to ensure idempotency
        existing_keys = set(
            PredictionSnapshot.objects.filter(checkpoint=checkpoint).values_list(
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
                    checkpoint=checkpoint,
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
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully persisted {created_count} prediction snapshot(s) for checkpoint '{checkpoint}' "
                f"({skipped_count} skipped as already existing)."
            )
        )
