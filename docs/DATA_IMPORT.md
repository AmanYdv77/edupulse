# EduPulse Institutional Data Import & Data Segregation Guide

## 1. Overview & Data Segregation Architecture

EduPulse strictly separates **synthetic demo data** from **real institutional academic data**:

| Attribute | Demo Data (`seed_demo`) | Real Institutional Data (`import_institute_data`) |
| :--- | :--- | :--- |
| **`data_origin` Field** | `"demo"` | `"real"` |
| **Allowed Environments** | `dev`, `e2e`, `test` (Blocked in `prod`) | `prod`, `test` for `--commit` (`dev` for validation dry-run) |
| **User Passwords** | Configured via `DEMO_USER_PASSWORD` | Unusable (`set_unusable_password()`) |
| **Predictive Signal** | Zero correlation by design (< 0.3 Pearson) | Authentic historical academic records |
| **Purge / Reset Safety** | `--reset-demo` deletes **only** `demo` rows | Protected from bulk seed purges |

---

## 2. Seeding Demo Data (`seed_demo`)

The `seed_demo` command generates a comprehensive academic structure (~3 departments, faculty members, ~60 students, courses, batches, subjects, internal assessments, and habit telemetry).

### Pre-conditions
- `DJANGO_ENV` must be `dev`, `e2e`, or `test`. (Exits with a security violation on `prod`).
- Database name must end in `_dev`, `_e2e`, or `_test`.
- `DEMO_USER_PASSWORD` environment variable must be set.

### Usage
```bash
# Seed demo dataset
python app/manage.py seed_demo

# Reset existing demo data before re-seeding
python app/manage.py seed_demo --reset-demo
```

### Safety Design
- Every created student profile has `data_origin="demo"`.
- `--reset-demo` deletes **only** student profiles and associated accounts with `data_origin="demo"`. Real student records (`data_origin="real"`) are never touched.
- Behavioral features (attendance, study hours, sleep) and examination marks are sampled **independently** from unrelated distributions. Pearson correlation is bounded below 0.3 to prevent models from learning spurious synthetic patterns.
- Displays non-negotiable warning banner:
  ```text
  WARNING: Demo data has no predictive signal by design. Never train on it.
  ```

---

## 3. Institutional Data Import (`import_institute_data`)

The `import_institute_data` command provides schema-validated, transactional ingestion of real university records.

### Execution Modes
1. **Validation Dry-Run (Default)**:
   - Evaluates file existence, headers, types, and constraints row by row.
   - Reports exact row, column, and error messages.
   - Writes **0 rows** to the database.
   - Allowed in any environment.
2. **Commit (`--commit`)**:
   - Executes validation first.
   - Wraps all database inserts/updates in a single `transaction.atomic()`.
   - Requires `DJANGO_ENV` to be `"prod"` or `"test"`.
   - Sets `data_origin="real"` on all created students.
   - Disables password login via `set_unusable_password()`.
   - Uses idempotent upserts so re-running with updated records avoids duplicates.

### Usage
```bash
# Validate CSV files in directory (dry-run mode)
python app/manage.py import_institute_data --data-dir path/to/csvs/

# Commit real data in production
DJANGO_ENV=prod python app/manage.py import_institute_data --data-dir path/to/csvs/ --commit

# Ingest specific files
python app/manage.py import_institute_data \
    --students path/to/students.csv \
    --subjects path/to/subjects.csv \
    --results path/to/results.csv \
    --commit
```

---

## 4. CSV Schema Specifications

### `students.csv`
Defines student personal and institutional identity.

| Column | Type | Required | Description / Constraints |
| :--- | :--- | :--- | :--- |
| `roll_no` | String | **Yes** | Unique institutional roll number (e.g. `24CSE001`). |
| `first_name` | String | **Yes** | Student first name. |
| `last_name` | String | **Yes** | Student last name. |
| `email` | String | **Yes** | Valid institutional email address. |
| `course_code` | String | **Yes** | Code of enrolled course (e.g. `BTCSE`). |
| `batch_code` | String | **Yes** | Code of academic batch (e.g. `2024-BTCSE`). |
| `admission_year` | Integer | **Yes** | Four-digit admission year (e.g. `2024`). |
| `current_semester`| Integer | No | Active semester (default: `1`). |
| `current_year` | Integer | No | Active study year (default: `1`). |
| `registration_no` | String | No | University registration / enrollment number. |
| `admission_type` | String | No | `Regular` or `Lateral Entry`. |
| `guardian_name` | String | No | Guardian name. |
| `guardian_phone` | String | No | Contact phone number. |
| `distance_from_home` | String | No | `Near`, `Moderate`, or `Far`. |
| `parental_education_level` | String | No | `High School`, `College`, or `Postgraduate`. |
| `family_income` | String | No | `Low`, `Medium`, or `High`. |
| `internet_access` | Boolean | No | `true` / `false` / `1` / `0`. |
| `access_to_resources` | String | No | `Low`, `Medium`, or `High`. |
| `learning_disabilities` | Boolean | No | `true` / `false` / `1` / `0`. |

### `subjects.csv`
Defines curriculum courses and credit weightage.

| Column | Type | Required | Description / Constraints |
| :--- | :--- | :--- | :--- |
| `code` | String | **Yes** | Unique subject code (e.g. `CS101`). |
| `title` | String | **Yes** | Full subject title. |
| `course_code` | String | **Yes** | Associated course code. |
| `semester` | Integer | **Yes** | Curriculum semester (1 to 12). |
| `credits` | Integer | **Yes** | Academic credit value (e.g. `4`). |
| `max_marks` | Integer | No | Total marks (default: `100`). |
| `internal_max` | Integer | No | Max internal marks (default: `30`). |
| `external_max` | Integer | No | Max external exam marks (default: `70`). |
| `subject_type` | String | No | `Theory` or `Practical` (default: `Theory`). |

### `results.csv`
Records official final subject examination marks.

| Column | Type | Required | Description / Constraints |
| :--- | :--- | :--- | :--- |
| `roll_no` | String | **Yes** | Foreign key matching `StudentProfile.roll_no`. |
| `subject_code` | String | **Yes** | Foreign key matching `Subject.code`. |
| `semester` | Integer | **Yes** | Semester number. |
| `internal_marks` | Integer | **Yes** | Marks obtained in internal component. |
| `external_marks` | Integer | **Yes** | Marks obtained in university examination. |
| `total_secured` | Integer | No | Combined score (auto-calculated if empty). |
| `grade_points` | Float | No | Grade point 0.0 - 10.0 (auto-calculated if empty). |
| `letter_grade` | String | No | Letter grade (e.g. `A`, `B`, `F`). |
| `exam_session` | String | No | Examination session name (e.g. `Winter 2024`). |

### `assessments.csv`
Records continuous evaluation / internal assessments uploaded by faculty.

| Column | Type | Required | Description / Constraints |
| :--- | :--- | :--- | :--- |
| `roll_no` | String | **Yes** | Student roll number. |
| `subject_code` | String | **Yes** | Subject code. |
| `semester` | Integer | **Yes** | Semester number. |
| `title` | String | **Yes** | Assessment title (e.g. `Midterm 1`, `Assignment 2`). |
| `assessment_type` | String | **Yes** | One of: `MIDTERM`, `ASSIGNMENT`, `QUIZ`, `LAB`, `PROJECT`. |
| `marks_obtained` | Float | **Yes** | Marks scored. |
| `max_marks` | Float | **Yes** | Maximum score possible. |

### `attendance.csv`
Records semester attendance percentage and behavioral survey indicators.

| Column | Type | Required | Description / Constraints |
| :--- | :--- | :--- | :--- |
| `roll_no` | String | **Yes** | Student roll number. |
| `semester` | Integer | **Yes** | Semester number. |
| `attendance_percentage` | Float | **Yes** | Percentage (0.0 to 100.0). |
| `hours_studied_per_week` | Float | No | Estimated weekly self-study hours. |
| `sleep_hours_per_night` | Float | No | Average sleep hours. |
| `motivation_level` | String | No | `Low`, `Medium`, or `High`. |
| `tutoring_sessions` | Integer | No | Attended tutoring sessions count. |
