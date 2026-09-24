# Model Card: Model B (Institutional Custom Model)

## 1. Model Details
- **Model Name:** EduPulse Model B (Institutional Performance Regressor)
- **Model Version:** Template / Initial Candidate
- **Deployment Slot:** `institute`
- **Candidate Algorithms Evaluated:** Naive Baseline (prior mean), Ridge Regression (L2), HistGradientBoostingRegressor
- **Framework:** scikit-learn
- **Target Variable:** Course percentage score `(total_secured / max_marks) * 100.0` (range 0.0 - 100.0)

## 2. Intended Use & Scope
- **Primary Use:** Calibrated early-warning forecasting based on historical records from the institution's own curriculum and grading distributions.
- **Scope:** Provides advisory forecasts for students and faculty advisors at established checkpoints during the active semester.
- **Strict Prohibitions:** Advisory only. Must NEVER be used for automated grading, academic discipline, admission decisions, scholarship eligibility, or punitive evaluations.

## 3. Data Source & Quality Disclosures
- **Dataset:** Institutional historical results and internal marks (`data_origin = 'real'`).
- **Demographic Separation:** Synthetic/demo records (`data_origin = 'demo'`) are strictly barred from entering training.
- **Minimum Eligibility Thresholds:**
  - Distinct students: >= 200
  - Total records: >= 1,000
  - Longitudinal coverage: >= 3 distinct semesters

## 4. Features & Governance
### Approved Features Ingested (v1 - Academic Only)
- `previous_score`: Student's previous semester percentage or SGPA equivalent.
- `internal_assessment_score`: Faculty-recorded continuous internal evaluation percentage.
- `attendance_percentage`: Official recorded classroom attendance.

### Approved Features Ingested (v2 - Habits Enabled)
- `hours_studied`: Self-reported study hours per week.
- `sleep_hours`: Self-reported nightly sleep duration.
- `tutoring_sessions`: Attendance at tutoring support sessions.
- `physical_activity`: Physical exercise/activity days per week.
*(Note: v2 features are enabled only when `MODEL_B_USE_HABITS=True` and longitudinal snapshot history exists).*

### Banned Protected Attributes & Demographics
All demographic characteristics (`gender`, `category`, `address_state`, `learning_disabilities`) and unapproved socio-economic proxies are strictly prohibited from entering model inputs.

## 5. Temporal Evaluation & Anti-Leakage Protocol
- **Temporal Holdout:** The latest academic semester is strictly reserved as an untouched test set. Models are fitted exclusively on earlier semesters.
- **Grouped Cross-Validation:** Folds are split using `GroupKFold` grouped by `student_id`. No student appears in both training and validation sets within any fold, preventing data leakage across repeated semester records.

## 6. Promotion Criteria
To replace Model A as the active scoring engine, Model B must satisfy:
1. Empirical superiority over the naive prior-semester baseline on the holdout test set.
2. An improvement of at least `2.0` RMSE points over Model A on the identical holdout test set.
3. Clean demographic fairness audit with no severe subgroup error disparities.

## 7. Demographic Fairness Audit
Audit results disaggregated by protected demographic attributes (`gender`, `category`) are computed offline during training and saved to the artifact directory. Groups with fewer than 20 students are suppressed to prevent re-identification and statistical distortion.
