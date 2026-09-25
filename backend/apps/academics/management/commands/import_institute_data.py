"""
Management command: import_institute_data

Validates and imports real institutional academic CSV data into EduPulse.
Guarded:
  - Default mode is dry-run validation (writes 0 rows).
  - --commit writes records in a single atomic transaction.
  - --commit is permitted ONLY when DJANGO_ENV is in ('prod', 'test').
  - Sets data_origin='real' for all imported student records.
  - Sets unusable passwords for all created user accounts.
  - Idempotent upserts (safe to re-run with updated or repeated CSVs).
"""

import csv
import os
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from academics.models import (
    School,
    Department,
    Course,
    Batch,
    Subject,
    StudentProfile,
    Result,
    SemesterResult,
    InternalAssessment,
)


class Command(BaseCommand):
    help = "Validate and import real institutional CSV data (students, subjects, results, assessments, attendance)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            help="Directory containing CSV files (students.csv, subjects.csv, results.csv, assessments.csv, attendance.csv).",
        )
        parser.add_argument("--students", type=str, help="Path to students.csv")
        parser.add_argument("--subjects", type=str, help="Path to subjects.csv")
        parser.add_argument("--results", type=str, help="Path to results.csv")
        parser.add_argument("--assessments", type=str, help="Path to assessments.csv")
        parser.add_argument("--attendance", type=str, help="Path to attendance.csv")
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Commit writes to database (requires DJANGO_ENV in ('prod', 'test')).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate CSVs without writing anything to the database (default).",
        )

    def handle(self, *args, **options):
        commit = options.get("commit", False)
        dry_run = options.get("dry_run", False) or not commit

        # 1. Environment Guard for --commit
        django_env = os.environ.get("DJANGO_ENV", "").strip().lower()
        if commit:
            if django_env not in ("prod", "test"):
                raise CommandError(
                    f"Security Violation: Real institutional data import with --commit is restricted "
                    f"to 'prod' and 'test' environments (got DJANGO_ENV='{django_env}'). "
                    f"Use default dry-run mode for schema validation in development."
                )

        # 2. Resolve CSV file paths
        data_dir = options.get("data_dir")
        file_paths = {
            "subjects": options.get("subjects"),
            "students": options.get("students"),
            "results": options.get("results"),
            "assessments": options.get("assessments"),
            "attendance": options.get("attendance"),
        }

        if data_dir:
            dir_path = Path(data_dir)
            if not dir_path.is_dir():
                raise CommandError(f"Specified --data-dir does not exist: {data_dir}")
            for key in file_paths:
                candidate = dir_path / f"{key}.csv"
                if candidate.is_file() and not file_paths[key]:
                    file_paths[key] = str(candidate)

        active_files = {k: v for k, v in file_paths.items() if v}
        if not active_files:
            raise CommandError("No input CSV files provided. Specify --data-dir or individual CSV flags.")

        self.stdout.write(
            self.style.NOTICE(
                f"Running import_institute_data in {'COMMIT' if commit else 'DRY-RUN (Validation)'} mode..."
            )
        )

        # 3. Row-by-Row Validation & Staging
        all_errors = []
        parsed_data = {}

        for key, path in active_files.items():
            if not os.path.isfile(path):
                all_errors.append({"file": path, "row": 0, "column": "FILE", "error": "File not found"})
                continue

            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                parsed_data[key] = rows
                errors = self.validate_csv_schema(key, rows, path)
                all_errors.extend(errors)

        if all_errors:
            self.stdout.write(self.style.ERROR(f"Validation FAILED with {len(all_errors)} error(s):"))
            for err in all_errors:
                self.stdout.write(
                    f"  [{err['file']}] Row {err['row']} Column '{err['column']}': {err['error']}"
                )
            raise CommandError(f"Validation failed with {len(all_errors)} errors. No records written.")

        self.stdout.write(self.style.SUCCESS("All CSV schemas and data rows passed validation."))

        if dry_run or not commit:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN COMPLETE: Verified all records. 0 rows written to database. "
                    "Use --commit in prod/test to persist."
                )
            )
            return

        # 4. Atomic Execution of Writes
        with transaction.atomic():
            stats = self.execute_import(parsed_data)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully committed import:\n"
                f"  - Subjects upserted: {stats['subjects']}\n"
                f"  - Students upserted: {stats['students']} (data_origin='real')\n"
                f"  - Subject Results upserted: {stats['results']}\n"
                f"  - Internal Assessments upserted: {stats['assessments']}\n"
                f"  - Semester Results / Attendance upserted: {stats['attendance']}"
            )
        )

    def validate_csv_schema(self, file_type, rows, file_path):
        errors = []
        if not rows:
            return [{"file": file_path, "row": 0, "column": "ALL", "error": "File is empty"}]

        required_columns = {
            "subjects": ["code", "title", "course_code", "semester", "credits"],
            "students": ["roll_no", "first_name", "last_name", "email", "course_code", "batch_code", "admission_year"],
            "results": ["roll_no", "subject_code", "semester", "internal_marks", "external_marks"],
            "assessments": ["roll_no", "subject_code", "semester", "title", "assessment_type", "marks_obtained", "max_marks"],
            "attendance": ["roll_no", "semester", "attendance_percentage"],
        }

        req = required_columns.get(file_type, [])
        first_row_cols = list(rows[0].keys())
        for col in req:
            if col not in first_row_cols:
                errors.append(
                    {"file": file_path, "row": 1, "column": col, "error": f"Missing required column header '{col}'"}
                )

        if errors:
            return errors

        # Validate rows
        for idx, row in enumerate(rows, start=2):
            if file_type == "students":
                if not row.get("roll_no", "").strip():
                    errors.append({"file": file_path, "row": idx, "column": "roll_no", "error": "roll_no cannot be empty"})
                email = row.get("email", "").strip()
                try:
                    validate_email(email)
                except ValidationError:
                    errors.append({"file": file_path, "row": idx, "column": "email", "error": f"Invalid email format: '{email}'"})
                try:
                    int(row.get("admission_year", "0"))
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "admission_year", "error": "admission_year must be integer"})

            elif file_type == "subjects":
                try:
                    sem = int(row.get("semester", "0"))
                    if sem < 1 or sem > 12:
                        errors.append({"file": file_path, "row": idx, "column": "semester", "error": "semester must be between 1 and 12"})
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "semester", "error": "semester must be integer"})
                try:
                    int(row.get("credits", "0"))
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "credits", "error": "credits must be integer"})

            elif file_type == "results":
                try:
                    int(row.get("semester", "0"))
                    int(row.get("internal_marks", "0"))
                    int(row.get("external_marks", "0"))
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "marks", "error": "Marks and semester must be numeric"})

            elif file_type == "assessments":
                valid_types = ["MIDTERM", "ASSIGNMENT", "QUIZ", "LAB", "PROJECT"]
                a_type = row.get("assessment_type", "").strip().upper()
                if a_type not in valid_types:
                    errors.append(
                        {"file": file_path, "row": idx, "column": "assessment_type", "error": f"Invalid assessment_type '{a_type}', expected one of {valid_types}"}
                    )
                try:
                    float(row.get("marks_obtained", "0"))
                    float(row.get("max_marks", "0"))
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "marks", "error": "marks_obtained and max_marks must be numeric"})

            elif file_type == "attendance":
                try:
                    att = float(row.get("attendance_percentage", "-1"))
                    if att < 0 or att > 100:
                        errors.append({"file": file_path, "row": idx, "column": "attendance_percentage", "error": "attendance_percentage must be 0-100"})
                except ValueError:
                    errors.append({"file": file_path, "row": idx, "column": "attendance_percentage", "error": "attendance_percentage must be numeric"})

        return errors

    def _get_or_create_course(self, course_code, dept_code=None):
        course = Course.objects.filter(code=course_code).first()
        if course:
            return course

        if not dept_code:
            if "CSE" in course_code:
                dept_code = "CSE"
            elif "ECE" in course_code:
                dept_code = "ECE"
            elif "ME" in course_code:
                dept_code = "MECH"
            else:
                dept_code = "GEN"

        school, _ = School.objects.get_or_create(
            code="SOET",
            defaults={"name": "School of Engineering & Technology"},
        )
        dept, _ = Department.objects.get_or_create(
            code=dept_code,
            defaults={
                "name": f"Department of {dept_code}",
                "school": school,
            },
        )
        course, _ = Course.objects.get_or_create(
            code=course_code,
            defaults={
                "name": course_code,
                "level": "UG",
                "duration_years": 4,
                "department": dept,
            },
        )
        return course

    def execute_import(self, parsed_data):
        stats = {"subjects": 0, "students": 0, "results": 0, "assessments": 0, "attendance": 0}

        # 1. Subjects
        if "subjects" in parsed_data:
            for row in parsed_data["subjects"]:
                course = self._get_or_create_course(row["course_code"].strip())
                Subject.objects.update_or_create(
                    code=row["code"].strip(),
                    defaults={
                        "title": row["title"].strip(),
                        "course": course,
                        "semester": int(row["semester"]),
                        "credits": int(row["credits"]),
                        "max_marks": int(row.get("max_marks", 100)),
                        "internal_max": int(row.get("internal_max", 30)),
                        "external_max": int(row.get("external_max", 70)),
                        "subject_type": row.get("subject_type", "Theory").strip(),
                    },
                )
                stats["subjects"] += 1

        # 2. Students (always data_origin='real' and unusable passwords)
        if "students" in parsed_data:
            for row in parsed_data["students"]:
                roll_no = row["roll_no"].strip()
                username = f"std_{roll_no.lower()}"
                email = row["email"].strip()

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "role": User.Role.STUDENT,
                        "first_name": row["first_name"].strip(),
                        "last_name": row["last_name"].strip(),
                        "email": email,
                        "is_staff": False,
                    },
                )
                user.first_name = row["first_name"].strip()
                user.last_name = row["last_name"].strip()
                user.email = email
                user.set_unusable_password()
                user.save()

                course = None
                if row.get("course_code"):
                    dept_code = row.get("department_code")
                    course = self._get_or_create_course(row["course_code"].strip(), dept_code=dept_code)

                batch = None
                if row.get("batch_code") and course:
                    batch, _ = Batch.objects.get_or_create(
                        batch_code=row["batch_code"].strip(),
                        defaults={"course": course, "admission_year": int(row["admission_year"])},
                    )

                def parse_bool(val, default=False):
                    if str(val).strip().lower() in ("true", "1", "yes"):
                        return True
                    if str(val).strip().lower() in ("false", "0", "no"):
                        return False
                    return default

                StudentProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "roll_no": roll_no,
                        "registration_no": row.get("registration_no", "").strip(),
                        "course": course,
                        "batch": batch,
                        "admission_year": int(row["admission_year"]),
                        "current_year": int(row.get("current_year", 1)),
                        "current_semester": int(row.get("current_semester", 1)),
                        "admission_type": row.get("admission_type", "Regular").strip(),
                        "guardian_name": row.get("guardian_name", "").strip(),
                        "guardian_phone": row.get("guardian_phone", "").strip(),
                        "distance_from_home": row.get("distance_from_home", "Moderate").strip(),
                        "parental_education_level": row.get("parental_education_level", "College").strip(),
                        "family_income": row.get("family_income", "Medium").strip(),
                        "internet_access": parse_bool(row.get("internet_access", True), True),
                        "access_to_resources": row.get("access_to_resources", "Medium").strip(),
                        "learning_disabilities": parse_bool(row.get("learning_disabilities", False), False),
                        "data_origin": "real",
                    },
                )
                stats["students"] += 1

        # 3. Results
        if "results" in parsed_data:
            for row in parsed_data["results"]:
                try:
                    student = StudentProfile.objects.get(roll_no=row["roll_no"].strip())
                    subject = Subject.objects.get(code=row["subject_code"].strip())
                except (StudentProfile.DoesNotExist, Subject.DoesNotExist):
                    continue

                int_m = int(row["internal_marks"])
                ext_m = int(row["external_marks"])
                total = int(row.get("total_secured") or (int_m + ext_m))
                gp = float(row.get("grade_points") or round(min(10.0, max(0.0, total / 10.0)), 1))

                Result.objects.update_or_create(
                    student=student,
                    subject=subject,
                    semester=int(row["semester"]),
                    defaults={
                        "internal_marks": int_m,
                        "external_marks": ext_m,
                        "total_secured": total,
                        "max_marks": subject.max_marks,
                        "credits": subject.credits,
                        "grade_points": gp,
                        "credit_points": round(gp * subject.credits, 1),
                        "letter_grade": row.get("letter_grade", "A" if total >= 80 else "B"),
                        "exam_session": row.get("exam_session", ""),
                    },
                )
                stats["results"] += 1

        # 4. Assessments
        if "assessments" in parsed_data:
            for row in parsed_data["assessments"]:
                try:
                    student = StudentProfile.objects.get(roll_no=row["roll_no"].strip())
                    subject = Subject.objects.get(code=row["subject_code"].strip())
                except (StudentProfile.DoesNotExist, Subject.DoesNotExist):
                    continue

                InternalAssessment.objects.update_or_create(
                    student=student,
                    subject=subject,
                    semester=int(row["semester"]),
                    title=row["title"].strip(),
                    defaults={
                        "assessment_type": row["assessment_type"].strip().upper(),
                        "marks_obtained": float(row["marks_obtained"]),
                        "max_marks": float(row["max_marks"]),
                        "is_submitted": True,
                    },
                )
                stats["assessments"] += 1

        # 5. Attendance & Semester Aggregates
        if "attendance" in parsed_data:
            for row in parsed_data["attendance"]:
                try:
                    student = StudentProfile.objects.get(roll_no=row["roll_no"].strip())
                except StudentProfile.DoesNotExist:
                    continue

                sem = int(row["semester"])
                att = float(row["attendance_percentage"])
                study_hrs = float(row.get("hours_studied_per_week", 15.0))
                sleep_hrs = float(row.get("sleep_hours_per_night", 7.0))
                mot = row.get("motivation_level", "Medium").strip()

                SemesterResult.objects.update_or_create(
                    student=student,
                    semester=sem,
                    defaults={
                        "attendance_percentage": att,
                        "hours_studied_per_week": study_hrs,
                        "sleep_hours_per_night": sleep_hrs,
                        "motivation_level": mot,
                        "is_published": True,
                    },
                )
                stats["attendance"] += 1

        return stats
