# EduPulse Testing Guide

This document outlines the testing architecture, suites, environment isolation guards, and execution instructions for EduPulse.

---

## 1. Test Architecture Overview

EduPulse employs a multi-tiered testing strategy ensuring reliability, security, accessibility, and machine learning integrity:

1. **Backend Unit & Integration Tests (`tests/test_*.py`)**:
   - Covers Django ORM models, constraints, API views, RBAC guards, rate limiting, caching, Celery tasks, and ML pipeline training/inference.
   - Runs against an isolated test database (`--reuse-db`).

2. **End-to-End (E2E) Browser Tests (`tests/e2e/test_*.py`)**:
   - Uses `pytest-playwright` driving real Chromium browsers.
   - Runs against a live Django server serving the production-built React SPA (`/app/`).
   - Verified on the dedicated `edupulse_e2e` database.
   - Strict browser hygiene: zero console errors, zero third-party external CDN requests, and strict Content-Security-Policy (CSP) validation.

3. **Frontend Unit & Component Tests (`frontend/src/**/*.test.tsx`)**:
   - Uses Vitest, React Testing Library, and MSW (Mock Service Worker).
   - Validates client-side logic, capability guards, forms, and chart accessibility tables.

---

## 2. Prerequisites & Setup

### Python Environment
Ensure virtual environment is active and dependencies are installed:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Playwright Browser Binaries
Install the required browser binaries (Chromium):
```bash
playwright install chromium
```

### Frontend Build (Required for E2E Tests)
E2E tests require the React SPA bundle to be built into `frontend/dist`:
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## 3. Running Tests

### Standard Fast Unit/Integration Tests
E2E tests are marked with `@pytest.mark.e2e` and excluded by default in `pyproject.toml` (`addopts = "-m 'not e2e' --reuse-db"`).
```bash
# Run all unit and integration tests
pytest -q
```

### End-to-End Browser Tests
To run all Playwright E2E tests:
```bash
# Run all E2E role journeys
pytest -m e2e

# Run with visible browser window (headed mode)
pytest -m e2e --headed

# Run a specific E2E test file
pytest tests/e2e/test_student_journey.py -m e2e
```

### Frontend Tests
```bash
cd frontend

# Run Vitest test suite
npm test

# Run TypeScript typecheck
npm run typecheck

# Run ESLint check
npm run lint
```

---

## 4. E2E Test Suite Matrix

| Test File | Role / Feature | Verified Behaviors |
| :--- | :--- | :--- |
| `tests/e2e/test_auth_and_login_hygiene.py` | Security & Auth | CSP headers, zero credential leak/autofill, capability navigation, sign-out |
| `tests/e2e/test_student_journey.py` | Student | Habit check-in form submission, reactive history update, semester results |
| `tests/e2e/test_teacher_journey.py` | Teacher | Teaching assignments list, continuous marks entry, early warning roster |
| `tests/e2e/test_hod_dean_scope.py` | HOD / Dean | Departmental analytics, route guard 403 enforcement |
| `tests/e2e/test_executive_privacy.py` | VC / Registrar | High-level KPIs, differential privacy, zero student PII in DOM |
| `tests/e2e/test_admin_model_registry.py` | SysAdmin | Model versions table, activation modal dialog, live slot promotion |

---

## 5. Failure Artifacts & Debugging

When an E2E test fails, the `e2e_page` fixture automatically captures a full-page screenshot and saves it to:
```
tests/e2e/artifacts/fail_<test_name>.png
```
These artifacts are ignored by `.gitignore` to prevent repository bloat.

---

## 6. Safety & Database Guards

- **Database Name Guard**: `tests/e2e/conftest.py` validates that `settings.DATABASES["default"]["NAME"]` contains `e2e` or `test`. Attempting to run E2E browser tests against a production or non-test database raises a critical safety violation and immediately aborts execution.
- **Third-Party Request Guard**: All browser requests are monitored; any outbound request to external domains or CDNs will fail the test.
