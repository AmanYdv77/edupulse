# EduPulse Application Core

This directory contains the Django application code, models, controllers, and templates for the **EduPulse Academic Prediction & Habit Telemetry Platform**.

---

## Directory Overview

*   `academics/` — Manages course structures, curriculum definitions, semester exam scores, and the **Habit Telemetry Engine** (`StudentHabitPreference`, `HabitCheckInLog`, and `sync_habits_to_semester_result`).
*   `accounts/` — Manages institutional RBAC (custom `User` model with roles: `student`, `teacher`, `hod`, `dean`, `admin`), student/staff profiles, and analytical dashboard controllers.
*   `resultplatform/` — Django project configuration, database settings, middleware, trusted origins, and master URL dispatching.
*   `templates/` — Monolith Academic Dark UI templates featuring pure CSS dark grey (`#090a0c`) and crisp white (`#ffffff`) styling with automated CSRF synchronization.

---

## Running Locally

```bash
# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`**.
