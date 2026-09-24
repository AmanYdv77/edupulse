"""
Management command to train, evaluate, and register Model A (baseline).
"""

import os
import platform
from pathlib import Path
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from edupulse_ml.train_a import train_baseline_pipeline
from predictions.models import ModelVersion


MODEL_CARD_TEMPLATE = """# Model Card: Model A (Academic Baseline)

## 1. Model Details
- **Model Name:** EduPulse Model A (Baseline Regressor)
- **Model Version:** {version}
- **Deployment Slot:** `baseline`
- **Algorithm:** {chosen_model}
- **Framework:** scikit-learn {sklearn_version}
- **Training Timestamp / Python Runtime:** Python {python_version}
- **Artifact File:** `{artifact_file}` (Stored in `MODEL_ARTIFACT_DIR`)
- **Dataset Fingerprint (SHA-256):** `{data_fingerprint}`

## 2. Intended Use & Scope
- **Primary Use:** Provides an initial academic performance benchmark and early-warning baseline before longitudinal institutional data is accumulated.
- **Scope:** Estimates end-of-semester course score percentage (0.0 to 100.0) from behavioral and prior academic telemetry.
- **Strict Prohibition:** Advisory only. Must NEVER be used for automated grading, discipline, admission decisions, or scholarship revocation.

## 3. Data Source & Quality Disclosures
- **Dataset:** Kaggle Student Performance Factors.
- **License / Terms:** Public sample dataset (verify the license on the dataset page).
- **Critical Disclaimer:** **The dataset is widely regarded as synthetic; metrics show the pipeline works, not real-world accuracy.**

## 4. Features & Governance
### Approved Features Ingested
{approved_features_list}

### Dropped Attributes & Ethical Governance
All demographic characteristics and unapproved proxy attributes were strictly stripped prior to model training:
- **Gender:** Protected demographic attribute (illegal/unethical to influence academic risk).
- **Learning Disabilities:** Protected health/accommodation data.
- **Family Income & Parental Education:** Socio-economic proxy variables excluded to prevent institutional bias.
- **Distance from Home & Internet Access:** Non-actionable commuting and infrastructure constraints.

## 5. Performance Metrics & Benchmark Comparison
Evaluation conducted on an untouched 20% holdout test split ({n_test_rows} samples) following 5-fold cross-validation on the training split ({n_train_rows} samples):

| Metric | Naive Baseline (Mean Dummy) | Model A ({chosen_model}) | Improvement |
|---|---|---|---|
| **RMSE** | {dummy_rmse:.4f} | {test_rmse:.4f} | {rmse_diff:+.4f} points |
| **MAE** | {dummy_mae:.4f} | {test_mae:.4f} | {mae_diff:+.4f} points |
| **R² Score** | {dummy_r2:.4f} | {test_r2:.4f} | {r2_diff:+.4f} |

### Classification Matrix at Pass Mark (40.0% Threshold)
- **True Pass (Actual Pass, Predicted Pass):** {tp}
- **True Fail (Actual Fail, Predicted Fail):** {tn}
- **False Pass (Actual Fail, Predicted Pass):** {fp}
- **False Fail (Actual Pass, Predicted Fail):** {fn}
- **Classification Accuracy:** {accuracy:.2%}

## 6. Limitations & Future Work
- Model A represents a baseline starting point.
- Under the EduPulse ML Contract, Model A will be replaced by Model B (Institutional Custom Model) only when Model B is trained on at least 3 semesters of real institutional data (`data_origin = 'real'`) and demonstrates a >= 2.0 RMSE improvement on holdout validation.
"""


class Command(BaseCommand):
    help = "Trains, evaluates, and registers Model A (baseline) from the Kaggle dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help="Directory containing StudentPerformanceFactors.csv (defaults to parent directory)",
        )

    def handle(self, *args, **options):
        # 1. Resolve CSV path
        data_dir_arg = options["data_dir"]
        if data_dir_arg:
            candidate_path = Path(data_dir_arg) / "StudentPerformanceFactors.csv"
            if not candidate_path.is_file():
                candidate_path = Path(data_dir_arg)  # maybe they passed full path to CSV
        else:
            # Check standard fallback locations
            parent_dir = Path(settings.BASE_DIR).parent
            candidate_path = parent_dir / "StudentPerformanceFactors.csv"
            if not candidate_path.is_file():
                candidate_path = parent_dir.parent / "StudentPerformanceFactors.csv"

        if not candidate_path.is_file():
            raise CommandError(
                f"StudentPerformanceFactors.csv not found at '{candidate_path}'. "
                f"Please pass --data-dir <directory_path>."
            )

        artifact_dir = Path(settings.MODEL_ARTIFACT_DIR)
        self.stdout.write(f"Reading dataset from: {candidate_path}")
        self.stdout.write(f"Writing artifacts to: {artifact_dir}")

        # 2. Run training pipeline
        summary = train_baseline_pipeline(
            csv_path=candidate_path,
            artifact_dir=artifact_dir,
            random_state=42,
        )

        # 3. Determine next sequential version for baseline slot
        existing_versions = ModelVersion.objects.filter(slot="baseline").values_list("version", flat=True)
        next_version = (max(existing_versions) + 1) if existing_versions else 1

        # 4. Register ModelVersion
        mv = ModelVersion.objects.create(
            slot="baseline",
            version=next_version,
            trained_on="Kaggle Student Performance Factors (public sample data)",
            n_train_rows=summary["n_train_rows"],
            n_test_rows=summary["n_test_rows"],
            metrics=summary,
            feature_names=summary["feature_names"],
            sklearn_version=sklearn.__version__,
            python_version=platform.python_version(),
            data_fingerprint=summary["data_fingerprint"],
            artifact_file=summary["artifact_file"],
            is_active=False,  # Safe deployment: requires manual activation
        )

        # 5. Generate docs/MODEL_CARD_A.md
        docs_dir = Path(settings.BASE_DIR).parent / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        model_card_path = docs_dir / "MODEL_CARD_A.md"

        approved_list_str = "\n".join(f"- `{f}`" for f in summary["feature_names"])
        test_m = summary["test_metrics"]
        dummy_m = summary["dummy_metrics"]
        cm = test_m["confusion_matrix"]

        card_content = MODEL_CARD_TEMPLATE.format(
            version=next_version,
            chosen_model=summary["chosen_model"],
            sklearn_version=sklearn.__version__,
            python_version=platform.python_version(),
            artifact_file=summary["artifact_file"],
            data_fingerprint=summary["data_fingerprint"],
            approved_features_list=approved_list_str,
            n_train_rows=summary["n_train_rows"],
            n_test_rows=summary["n_test_rows"],
            dummy_rmse=dummy_m["rmse"],
            test_rmse=test_m["rmse"],
            rmse_diff=test_m["rmse"] - dummy_m["rmse"],
            dummy_mae=dummy_m["mae"],
            test_mae=test_m["mae"],
            mae_diff=test_m["mae"] - dummy_m["mae"],
            dummy_r2=dummy_m["r2"],
            test_r2=test_m["r2"],
            r2_diff=test_m["r2"] - dummy_m["r2"],
            tp=cm["true_pass"],
            tn=cm["true_fail"],
            fp=cm["false_pass"],
            fn=cm["false_fail"],
            accuracy=cm["classification_accuracy"],
        )
        model_card_path.write_text(card_content, encoding="utf-8")

        # 6. Report summary to stdout
        self.stdout.write(self.style.SUCCESS(f"\nModel A successfully trained and registered (id={mv.id}, v{next_version})!"))
        self.stdout.write(f"Chosen Algorithm: {summary['chosen_model']}")
        self.stdout.write(f"CV RMSE:         {summary['cv_rmse']:.4f}")
        self.stdout.write(f"Test RMSE:       {test_m['rmse']:.4f} (Dummy: {dummy_m['rmse']:.4f})")
        self.stdout.write(f"Test R2 Score:   {test_m['r2']:.4f} (Dummy: {dummy_m['r2']:.4f})")
        self.stdout.write(f"Model Card:      {model_card_path}")
        self.stdout.write(self.style.NOTICE(f"\nTo activate this model, run:\n  python app/manage.py models_activate {mv.id}"))
