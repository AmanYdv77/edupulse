# 🎓 EduPulse: Student Performance Prediction & Habit Telemetry Platform

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![Scikit--Learn](https://img.shields.io/badge/Scikit--Learn-ML%20Inference-orange.svg)](https://scikit-learn.org/)
[![Theme](https://img.shields.io/badge/Design%20System-Stitch%20Monolith%20Dark-white.svg)]()

EduPulse is an institutional Academic Information System and Predictive Telemetry Engine built with **Django 6**, **Scikit-Learn**, and the **Stitch "Monolith Academic" Design System**.

Unlike traditional Student Information Systems (SIS) that record student grades only after final exams (post-mortem analysis), EduPulse integrates **continuous student habit telemetry** with a **Dual-Model ML Architecture** to detect academic risks and provide prescriptive interventions before semester exams take place.

---

## 🌟 Key Features & Innovations

### 1. 🧠 Dual-Model ML Architecture
*   **Model 1 (Academic Baseline Prior)**: Computes a baseline trajectory using historical semester exams, mid-term internal assessments ($M_{internal} \in [0, 30]$), and course difficulty weights.
*   **Model 2 (Dynamic Behavioral Multiplier)**: Dynamically scales and calibrates expected subject scores using continuous lifestyle vectors:
    *   Weekly Study Hours ($0 - 60$ hrs)
    *   Sleep Consistency ($3 - 12$ hrs/night)
    *   Motivation Indices (Low / Medium / High)
    *   Tutoring Attendance & Physical Activity
    *   Daily Attendance Tracking ($0 - 100\%$)

### 2. ⚡ Flexible Habit Collection (Daily vs. Weekly Cadence)
To prevent logging fatigue, students choose their preferred input rhythm:
*   **Daily Quick-Check (30 sec)**: High-frequency tracking of daily study hours, sleep duration, and motivation streaks.
*   **Weekly Summary (2 min)**: Low-frequency aggregated summary for busy weekends.
*   **Automated Normalization**: A rolling 7-day mathematical aggregation pipeline converts daily inputs into normalized weekly metrics:
    $$\text{Normalized Weekly Study} = \left(\frac{1}{N}\sum_{i=1}^N \text{Daily Study}_i\right) \times 7$$

### 3. 🎯 Faculty Early Warning & Risk Radar
*   **At-Risk Detection**: Automatically flags students whose forecasted subject marks drop below the university passing threshold ($< 40\%$).
*   **Root-Cause Diagnostics**: Isolates whether failure is driven by academic gaps (low internal test marks) or behavioral deficits (study volume $< 8$ hrs/week or attendance $< 75\%$).
*   **Direct Interventions**: Allows faculty to trigger advising sessions or revision assignments.

### 4. 🎨 Stitch "Monolith Academic" Design System
*   **Strict Dual-Tone Color Palette**:
    *   **Canvas & Surfaces**: Deep Charcoal & Dark Grey (`#090a0c`, `#0e1014`, `#14161c`, `#1b1e26`)
    *   **Text & Accents**: Crisp High-Contrast White (`#ffffff`)
    *   **Muted Typography**: Neutral Grey (`#9da3b4`, `#5e6475`)
    *   **Badges**: Monochromatic high-contrast risk tags (`tag-high-risk`, `tag-moderate-risk`, `tag-low-risk`).
*   **Modern Typography**: `Geist` / `Inter` for layout and `JetBrains Mono` for data and telemetry readouts.

### 5. 🛡️ Robust CSRF Synchronization & Session Reliability
*   **Client-Side Auto-Synchronizer**: Automatically detects browser Back/Forward navigation (`pageshow` / bfcache) and updates form tokens with the active `csrftoken` cookie before submission.
*   **Graceful Recovery**: Includes custom `403_csrf.html` with one-click reload recovery.

---

## 🏛️ System Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │           EduPulse Web Application           │
                       └──────────────────────┬───────────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
       ┌────────────────────────┐                          ┌────────────────────────┐
       │     Student Portal     │                          │     Faculty Portal     │
       └────────────┬───────────┘                          └────────────┬───────────┘
                    │                                                   │
     ┌──────────────┴──────────────┐                      ┌─────────────┴─────────────┐
     ▼                             ▼                      ▼                           ▼
[Habit Check-In]          [AI Predictions]         [At-Risk Radar]            [Dept Ledger]
(Daily / Weekly)          (Risk Diagnostics)       (Early Warnings)           (Master Transcripts)
     │                             ▲                      ▲                           │
     │                             │                      │                           │
     └──────────────┬──────────────┘                      └─────────────┬─────────────┘
                    │                                                   │
                    ▼                                                   ▼
       ┌────────────────────────┐                          ┌────────────────────────┐
       │   sync_habits_to_sem   │                          │   Scoped Permissions   │
       │ (7-Day Rolling Normal) │                          │  (Teacher/HOD/Dean/VC) │
       └────────────┬───────────┘                          └────────────┬───────────┘
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              │
                                              ▼
                             ┌───────────────────────────────────┐
                             │       Relational DB Schema        │
                             │ (Users, Academics, Habits, Sem)   │
                             └───────────────────────────────────┘
```

---

## 🔑 Demo Accounts & Credentials

The platform includes pre-seeded roles ready for testing:

| Role | Username | Password | Purpose & Scope |
| :--- | :--- | :--- | :--- |
| **Student** | `25-engg-cse-ug-001` | `password123` | Interactive Habit Logging, AI Forecast Matrix, Academic Transcripts |
| **Teacher / Faculty** | `cse_fac01` | `password123` | Department Cohort Monitoring, Early Warning Radar, Student Interventions |
| **Administrator** | `Aman_Yadav` | `password123` | University-wide administration, curriculum setup, data imports |

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
*   Python 3.11 or 3.12 installed
*   Git

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/AmanYdv77/Students_Performance_Prediction.git
cd Students_Performance_Prediction

# Create and activate virtual environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# On macOS/Linux:
# source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
python app/manage.py migrate
```

### 4. Start the Development Server
```bash
python app/manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser to access the platform.

---

## 📋 Testing the Workflow

### Student Workflow
1. Navigate to `http://127.0.0.1:8000/accounts/login/`.
2. Sign in with **`25-engg-cse-ug-001`** / **`password123`**.
3. On the **Command Dashboard**, review forecasted marks, attendance, and habit streaks.
4. Click **Log Habits** in the sidebar (or visit `/habits/check-in/`):
   * Switch between **Daily Quick-Check** and **Weekly Summary** modes.
   * Adjust study and sleep sliders and record a check-in.
5. Click **AI Predictions** in the sidebar (or visit `/my-predictions/`) to view the updated subject forecast matrix and prescriptive guidance.

### Faculty Workflow
1. Click **Exit** in the sidebar footer and sign in with **`cse_fac01`** / **`password123`**.
2. On the **Faculty Dashboard**, review monitored student counts and at-risk metrics.
3. Click **At-Risk Radar** (`/at-risk/`) to view flagged students with failing course trajectories.
4. Click **Dept Records** (`/results-overview/`) to view the department-scoped performance ledger.

---

## 📂 Project Structure

```
Student_Performance_Prediction/
├── app/
│   ├── academics/                 # Curriculum, results, and habit tracking
│   │   ├── migrations/            # Database schema migrations
│   │   ├── forms.py               # Telemetry and preference forms
│   │   ├── models.py              # Models: HabitCheckInLog, StudentHabitPreference, etc.
│   │   ├── analytics_engine.py    # Multi-Tier 5-number summary, topper, & failure engine
│   │   └── views.py
│   ├── accounts/                  # User identity, RBAC, and dashboards
│   │   ├── models.py              # Custom User with role hierarchy
│   │   ├── views.py               # Dashboard, prediction, and radar controllers
│   │   ├── analytics_views.py     # Role-based analytics dispatcher & JSON query API
│   │   └── urls.py                # App routing
│   ├── resultplatform/            # Django root configuration
│   │   ├── settings.py            # Trusted origins, CSRF, and session settings
│   │   └── urls.py                # Master URL dispatcher
│   └── templates/                 # Stitch Monolith Dark templates
│       ├── base.html              # Sidebar, topbar, and CSRF synchronizer
│       ├── 403_csrf.html          # Monolith security recovery view
│       ├── home.html              # Student & Faculty dashboards
│       ├── habit_checkin.html     # Telemetry logging studio
│       ├── my_predictions.html    # Dual-Model AI diagnostics
│       ├── at_risk_students.html  # Faculty Early Warning Radar
│       ├── my_results.html        # Academic transcripts
│       ├── scoped_results.html    # Departmental ledger
│       ├── analytics/             # Multi-Tier Analytics Cockpits (Student, Teacher, HOD, Dean, VC)
│       └── registration/
│           └── login.html         # High-contrast sign-in page
├── scripts/                       # Seeding and model training utilities
│   ├── import_university_data.py  # Seed university hierarchy
│   ├── seed_academics.py          # Seed curriculum and test results
│   ├── seed_kaggle_features.py    # Seed behavioral features
│   ├── seed_sample_users.py       # Seed test accounts
│   └── train_predictor.py         # Train Scikit-Learn inference pipeline
├── requirements.txt               # Dependencies
├── .gitignore                     # Git exclusions (data, docs, venv)
└── Readme.md                      # Project documentation
```

---

## 📄 License & Attribution

Developed for academic research and institutional result management. Built with modern web engineering and data science best practices.
