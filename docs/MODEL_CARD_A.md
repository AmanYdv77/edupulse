# Model Card: Model A (Academic Baseline)

## 1. Model Details
- **Model Name:** EduPulse Model A (Baseline Regressor)
- **Model Version:** 1
- **Deployment Slot:** `baseline`
- **Algorithm:** ridge_alpha_1.0
- **Framework:** scikit-learn 1.8.0
- **Training Timestamp / Python Runtime:** Python 3.12.4
- **Artifact File:** `model_a_baseline.joblib` (Stored in `MODEL_ARTIFACT_DIR`)
- **Dataset Fingerprint (SHA-256):** `0159b524d7579b3210d760db3748d1cdd4c3d5a451d50b28d7bafede2f02de76`

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
- `attendance_percentage`
- `hours_studied`
- `sleep_hours`
- `previous_score`
- `tutoring_sessions`
- `physical_activity`

### Dropped Attributes & Ethical Governance
All demographic characteristics and unapproved proxy attributes were strictly stripped prior to model training:
- **Gender:** Protected demographic attribute (illegal/unethical to influence academic risk).
- **Learning Disabilities:** Protected health/accommodation data.
- **Family Income & Parental Education:** Socio-economic proxy variables excluded to prevent institutional bias.
- **Distance from Home & Internet Access:** Non-actionable commuting and infrastructure constraints.

## 5. Performance Metrics & Benchmark Comparison
Evaluation conducted on an untouched 20% holdout test split (20 samples) following 5-fold cross-validation on the training split (80 samples):

| Metric | Naive Baseline (Mean Dummy) | Model A (ridge_alpha_1.0) | Improvement |
|---|---|---|---|
| **RMSE** | 10.3555 | 3.0329 | -7.3226 points |
| **MAE** | 8.5783 | 2.4078 | -6.1705 points |
| **R² Score** | -0.0113 | 0.9133 | +0.9246 |

### Classification Matrix at Pass Mark (40.0% Threshold)
- **True Pass (Actual Pass, Predicted Pass):** 19
- **True Fail (Actual Fail, Predicted Fail):** 1
- **False Pass (Actual Fail, Predicted Pass):** 0
- **False Fail (Actual Pass, Predicted Fail):** 0
- **Classification Accuracy:** 100.00%

## 6. Limitations & Future Work
- Model A represents a baseline starting point.
- Under the EduPulse ML Contract, Model A will be replaced by Model B (Institutional Custom Model) only when Model B is trained on at least 3 semesters of real institutional data (`data_origin = 'real'`) and demonstrates a >= 2.0 RMSE improvement on holdout validation.
