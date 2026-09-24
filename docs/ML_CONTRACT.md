# ML Contract

## 1. Prediction Question
For each student and subject, at designated checkpoints during the semester, estimate the end-of-semester percentage and whether it will fall below the pass mark.

## 2. Target and Pass Mark
- **Target:** Subject percentage = `(total marks secured / maximum marks) * 100` (float between 0.0 and 100.0).
- **PASS_MARK_PERCENT:** `40.0` (Institutional standard minimum percentage required to pass a course).
- **At-Risk Definition:** Any predicted end-of-semester score strictly below `PASS_MARK_PERCENT` (score < 40.0).

## 3. Approved Features Table

| name | type | range/unit | source | available when | model A (baseline) | model B (institute) | approved? |
|---|---|---|---|---|---|---|---|
| `attendance_percentage` | float | 0.0 - 100.0 (%) | Academic records / attendance logs | Real-time & Checkpoints | Yes | Yes | Approved |
| `hours_studied` | float | 0.0 - 168.0 (hrs/week) | Self-reported habit logs | Checkpoints | Yes | Yes | Approved |
| `sleep_hours` | float | 0.0 - 24.0 (hrs/day) | Self-reported habit logs | Checkpoints | Yes | Yes | Approved |
| `previous_score` | float | 0.0 - 100.0 (%) | Previous semester academic result | Beginning of semester | Yes | Yes | Approved |
| `tutoring_sessions` | int | 0 - 50 (sessions/month) | Self-reported habit logs | Checkpoints | Yes | Yes | Approved |
| `physical_activity` | float | 0.0 - 50.0 (hrs/week) | Self-reported habit logs | Checkpoints | Yes | Yes | Approved |
| `internal_assessment_score` | float | 0.0 - 100.0 (%) | Faculty internal marks entries | Checkpoint 2 (Mid-sem) | No | Yes | Approved |

## 4. Excluded Attributes and Why

### Never Inputs (Strictly Banned Protected Attributes)
- `gender`: Protected demographic characteristic. Legally and ethically prohibited from biasing predictions or risk classification.
- `category`: Caste / reservation status. Protected identity; illegal to penalize or flag students based on affirmative action categories.
- `address_state`: Regional origin. Protected from geographic profiling or institutional bias.
- `learning_disabilities`: Protected health / accommodation data. Accommodations must be supported without algorithmic penalties.

*Note:* Protected attributes may still be accessed in anonymized fairness audit reports (Task A18) to detect disparities, but MUST NEVER be provided as inputs to any predictive model.

### Excluded Attributes (Review Required, Currently Rejected)
- `family_income`: Socio-economic status should not bias institutional expectations.
- `parental_education_level`: Background characteristic outside student agency.
- `distance_from_home`: Commuting constraint; non-actionable as an academic predictor.
- `internet_access`: Infrastructure constraint; institutional resources should provide parity.
- `access_to_resources`: Subjective survey metric vulnerable to reporting bias.

*Policy:* Any review-required attribute remains strictly excluded unless explicitly amended and approved with documented empirical justification in this contract.

## 5. Checkpoints
- **Checkpoint 1 (Week 4):** Early attendance and habit check-in trends combined with previous semester standing.
- **Checkpoint 2 (Mid-Semester):** Updated attendance, habit logs, and mid-term internal assessment scores.

## 6. Minimum Data to Train Model B
- Minimum students: `students >= 200`
- Minimum total sample rows: `rows >= 1000`
- Minimum longitudinal history: At least 3 fully published semesters of non-synthetic institutional records (`data_origin = 'real'`).

## 7. Promotion Rule
Model B (institutional custom model) replaces Model A (public baseline) if and only if:
1. It is trained exclusively on non-demo data (`data_origin == 'real'`).
2. It demonstrates an improvement over both the naive baseline (prior-semester average) and Model A on a strict latest-semester holdout split by at least `2.0` RMSE points.
3. It adheres strictly to the approved feature set in Section 3 with zero leakage and zero protected attributes.

## 8. How Predictions May Be Used
- **Advisory & Supportive Only:** Predictions serve solely as early warnings to trigger proactive academic mentoring, tutoring referrals, and study habit recommendations.
- **Strict Prohibitions:** Predictions MUST NEVER be used for automated grading, academic discipline, admission decisions, scholarship eligibility, or punitive evaluations.

## 9. Review & Governance
- **Status:** Active & Enforced
- **Governance Framework:** EduPulse Academic Integrity & Machine Learning Governance
