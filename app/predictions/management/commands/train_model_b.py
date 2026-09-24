"""
Management command to train, evaluate, and register Model B (Institute Custom Model).
Enforces real-data checks, environment constraints, and minimum dataset thresholds.
"""

import os
import sys
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from edupulse_ml.datasets.institute import load_institute_dataset, InsufficientDataError
from edupulse_ml.train_b import train_and_evaluate_model_b, split_temporal_holdout
from edupulse_ml.evaluate import evaluate_regression
from predictions.models import ModelVersion
from predictions.services import PredictorService
from predictions.promotion import should_promote


class Command(BaseCommand):
    help = "Trains, evaluates, and registers Model B (Institutional Custom Model) on verified real institutional records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-real-data",
            action="store_true",
            default=False,
            help="Confirmation that data is verified institutional records, not synthetic or demo data.",
        )
        parser.add_argument(
            "--use-habits",
            action="store_true",
            default=False,
            help="Enable habit telemetry features (v2). Default is False (academic signals only).",
        )

    def handle(self, *args, **options):
        # 1. Flag Confirmation Guard
        if not options.get("confirm_real_data"):
            raise CommandError(
                "Execution aborted: You must explicitly pass --confirm-real-data to confirm "
                "that institutional records are verified and eligible for training."
            )

        # 2. Environment Guard
        django_env = os.environ.get("DJANGO_ENV", "").strip().lower()
        if django_env not in ("prod", "test"):
            raise CommandError(
                f"Security Violation: train_model_b can only be executed in 'prod' or 'test' environments. "
                f"Current DJANGO_ENV is '{django_env or 'unspecified'}'."
            )

        self.stdout.write(self.style.NOTICE("Loading verified real-world institutional records..."))

        # 3. Load Dataset & Enforce Thresholds
        use_habits = options.get("use_habits", False) or getattr(settings, "MODEL_B_USE_HABITS", False)
        try:
            df = load_institute_dataset(enforce_thresholds=True, use_habits=use_habits)
        except (InsufficientDataError, RuntimeError) as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(df)} records across {df['student_id'].nunique()} students "
                f"and {df['semester'].nunique()} semesters."
            )
        )

        # 4. Train and Evaluate Candidate Models
        self.stdout.write("Running grouped cross-validation and temporal holdout evaluation...")
        train_results = train_and_evaluate_model_b(df, use_habits=use_habits)

        candidate_name = train_results["candidate_name"]
        candidate_metrics = train_results["candidate_metrics"]
        baseline_metrics = train_results["baseline_metrics"]
        holdout_semester = train_results["latest_holdout_semester"]

        # 5. Evaluate Incumbent Model A on Holdout Set (if active)
        incumbent_metrics = None
        active_model_a = PredictorService.get_active_model_version("baseline")
        if active_model_a:
            try:
                _, test_df = split_temporal_holdout(df)
                # Check if test_df has features required by Model A
                missing_feats = [f for f in active_model_a.feature_names if f not in test_df.columns]
                if not missing_feats:
                    model_a_loaded = PredictorService.load("baseline")
                    preds_a = model_a_loaded.predict(test_df[active_model_a.feature_names])
                    incumbent_metrics = evaluate_regression(test_df["target_percentage"].values, preds_a)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not score holdout with Model A: {e}"))

        # 6. Promotion Evaluation
        is_promotable, reasons = should_promote(
            candidate_metrics=candidate_metrics,
            incumbent_metrics=incumbent_metrics,
            baseline_metrics=baseline_metrics,
        )

        # 7. Register Candidate in Model Registry
        latest_version = (
            ModelVersion.objects.filter(slot="institute").order_by("-version").values_list("version", flat=True).first()
            or 0
        )
        new_version = latest_version + 1

        all_metrics = {
            "holdout_semester": holdout_semester,
            "cv_scores": train_results["cv_scores"],
            "candidate_metrics": candidate_metrics,
            "baseline_metrics": baseline_metrics,
            "incumbent_metrics": incumbent_metrics,
            "promotion_decision": {
                "promoted": is_promotable,
                "reasons": reasons,
            },
        }

        with transaction.atomic():
            mv = ModelVersion.objects.create(
                slot="institute",
                version=new_version,
                trained_on=f"Institutional records ({len(df)} rows, {df['student_id'].nunique()} students)",
                n_train_rows=train_results["n_train_rows"],
                n_test_rows=train_results["n_test_rows"],
                metrics=all_metrics,
                feature_names=train_results["feature_names"],
                sklearn_version=sklearn.__version__,
                python_version=sys.version.split()[0],
                data_fingerprint=train_results["data_fingerprint"],
                artifact_file=train_results["artifact_file"],
                is_active=False,  # Never activate automatically!
            )

        # 8. Output Results & Decision
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Registered Model B Candidate (id={mv.id}, institute v{new_version})"))
        self.stdout.write(f"Algorithm:       {candidate_name}")
        self.stdout.write(f"Features:        {', '.join(train_results['feature_names'])}")
        self.stdout.write(f"Holdout Sem:     Semester {holdout_semester}")
        self.stdout.write(f"Holdout RMSE:    {candidate_metrics['rmse']:.3f}")
        self.stdout.write(f"Holdout MAE:     {candidate_metrics['mae']:.3f}")
        self.stdout.write(f"Holdout R2:      {candidate_metrics['r2']:.3f}")
        self.stdout.write(f"Naive Baseline:  RMSE {baseline_metrics['rmse']:.3f}")
        if incumbent_metrics:
            self.stdout.write(f"Model A (Hold):  RMSE {incumbent_metrics['rmse']:.3f}")
        else:
            self.stdout.write("Model A (Hold):  Not Available / Incomparable")

        self.stdout.write("-" * 60)
        if is_promotable:
            self.stdout.write(self.style.SUCCESS("PROMOTION STATUS: RECOMMENDED"))
            for r in reasons:
                self.stdout.write(f"  [+] {r}")
            self.stdout.write(
                self.style.NOTICE(
                    f"\nTo activate this model as the active institute model, run:\n"
                    f"  python app/manage.py models_activate {mv.id}\n"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("PROMOTION STATUS: NOT RECOMMENDED"))
            for r in reasons:
                self.stdout.write(f"  [-] {r}")
            self.stdout.write("\nCandidate registered for audit records but not recommended for activation.\n")
        self.stdout.write("=" * 60 + "\n")
