# 🎓 EduPulse: Student Performance Prediction & Habit Telemetry Platform

An enterprise-grade Academic Information System and Predictive Telemetry Engine built with **Django 6**, **Scikit-Learn**, and the **Stitch "Monolith Academic" Design System**.

---

## 🌟 Key Highlights

*   **Dual-Model ML Architecture**:
    *   **Model 1 (Academic Baseline)**: Predicts expected performance from multi-semester exam history and internal test assessments.
    *   **Model 2 (Behavioral Multiplier)**: Dynamically scales outcomes using continuous student habit telemetry (weekly study volume, sleep consistency, motivation levels).
*   **Flexible Habit Telemetry**:
    *   **Daily Quick-Check (30 sec)**: High-frequency daily study and sleep log.
    *   **Weekly Summary (2 min)**: Aggregated weekend reflection.
    *   Streak tracking and automated rolling 7-day normalization.
*   **Faculty Early Warning Radar**:
    *   Identifies students trending towards subject failure ($< 40\%$) before final exams take place.
    *   Attribution diagnostics (study deficits vs. attendance shortfalls).
*   **Monolith Academic Design System**:
    *   High-contrast, dual-tone aesthetic: **Dark Grey** (`#090a0c`, `#14161c`) + **Crisp White** (`#ffffff`).
    *   Automatic client-side CSRF token synchronization preventing back-forward cache mismatches.

---

## 🚀 Quick Start

### 1. Prerequisites & Environment
```bash
# Clone and enter workspace
cd Student_Performance_Prediction

# Activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Database Migrations & Server
```bash
python app/manage.py migrate
python app/manage.py runserver
```
Navigate to: **`http://127.0.0.1:8000/`**

---

## 🔑 Demo Accounts

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Student** | `25-engg-cse-ug-001` | `password123` | Log habits, view AI forecasts & transcripts |
| **Teacher** | `cse_fac01` | `password123` | Monitor cohort, inspect At-Risk Radar |
| **Admin** | `Aman_Yadav` | `password123` | Institutional management & data imports |

---

## 📂 Documentation Directory (`/docs`)

*   [`DUAL_ML_AND_HABIT_TELEMETRY.md`](docs/DUAL_ML_AND_HABIT_TELEMETRY.md) — Comprehensive technical whitepaper on the Dual-Model ML architecture and normalization algorithms.
*   [`DATABASE_DESIGN.md`](docs/DATABASE_DESIGN.md) — Relational schema specifications, personal vs. academic separation, and telemetry tables.
*   [`RESULT_PLATFORM_BLUEPRINT.md`](docs/RESULT_PLATFORM_BLUEPRINT.md) — Platform blueprint v2.0 covering architecture, user journeys, and implementation status.
*   [`CODE_EXPLANATION_HANDBOOK.md`](docs/CODE_EXPLANATION_HANDBOOK.md) — Line-by-line developer handbook explaining models, views, forms, and security scripts.
*   [`PROJECT_PRESENTATION.md`](docs/PROJECT_PRESENTATION.md) — Ready-to-present slide deck for academic project guides and evaluators.
