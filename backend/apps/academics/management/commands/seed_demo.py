"""
Management command: seed_demo

Seeds realistic demo data across ~3 departments (~60 students) with data_origin='demo'.
Guarded: Prohibited in production (refuses execution if DJANGO_ENV=prod or non-dev/e2e db).
Independent telemetry: Behavioral metrics and academic marks are generated independently (no synthetic correlation).
"""

import os
import random
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from academics.models import (
    University,
    School,
    Department,
    Course,
    Batch,
    Subject,
    TeacherProfile,
    StudentProfile,
    TeachingAssignment,
    Result,
    SemesterResult,
    InternalAssessment,
    StudentHabitPreference,
    HabitCheckInLog,
)
from academics.demo_data import (
    UNIVERSITY_DATA,
    SCHOOL_DATA,
    ADMIN_USERS,
    DEPARTMENTS_DATA,
    LAST_NAMES,
)

BANNER = """
======================================================================
WARNING: Demo data has no predictive signal by design. Never train on it.
======================================================================
"""


class Command(BaseCommand):
    help = "Seed institutional demo data (guarded to dev/e2e environments, data_origin='demo')."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help="Purge existing demo data (data_origin='demo') before seeding.",
        )

    def handle(self, *args, **options):
        # 1. Environment & Database Safety Guards
        django_env = os.environ.get("DJANGO_ENV", "").strip().lower()
        if django_env == "prod":
            raise CommandError(
                "Security Violation: seed_demo command is prohibited in production environment (DJANGO_ENV=prod)."
            )

        if django_env and django_env not in ("dev", "e2e", "test"):
            raise CommandError(
                f"Security Violation: seed_demo only allowed in dev or e2e environments (got DJANGO_ENV={django_env})."
            )

        db_name = settings.DATABASES["default"].get("NAME", "")
        if not (db_name.endswith("_dev") or db_name.endswith("_e2e") or db_name.endswith("_test")):
            raise CommandError(
                f"Security Violation: seed_demo requires a database ending with '_dev', '_e2e', or '_test'. Target was '{db_name}'."
            )

        # 2. Require DEMO_USER_PASSWORD
        demo_password = os.environ.get("DEMO_USER_PASSWORD")
        if not demo_password:
            raise CommandError(
                "DEMO_USER_PASSWORD environment variable is required to seed demo users."
            )

        # 3. Print Non-Negotiable Warning Banner
        self.stdout.write(self.style.WARNING(BANNER.strip()))

        reset_demo = options.get("reset_demo", False)

        with transaction.atomic():
            # 4. Reset demo data if requested (leaving real data untouched)
            if reset_demo:
                self.stdout.write("Purging existing demo data (data_origin='demo')...")
                demo_students = StudentProfile.objects.filter(data_origin="demo")
                demo_user_ids = list(demo_students.values_list("user_id", flat=True))

                # Delete demo student profiles (cascades to results, assessments, habits)
                deleted_students_count, _ = demo_students.delete()
                # Delete corresponding user accounts
                deleted_users_count, _ = User.objects.filter(id__in=demo_user_ids).delete()
                self.stdout.write(
                    f"Purged {deleted_students_count} demo student profiles and {deleted_users_count} users."
                )

            # 5. Seed University & School
            univ, _ = University.objects.get_or_create(
                code=UNIVERSITY_DATA["code"],
                defaults={
                    "name": UNIVERSITY_DATA["name"],
                    "established_year": UNIVERSITY_DATA["established_year"],
                },
            )

            school, _ = School.objects.get_or_create(
                code=SCHOOL_DATA["code"],
                defaults={
                    "name": SCHOOL_DATA["name"],
                    "university": univ,
                },
            )

            # 6. Seed Admin / Leadership Users
            for admin_info in ADMIN_USERS:
                user, created = User.objects.get_or_create(
                    username=admin_info["username"],
                    defaults={
                        "role": getattr(User.Role, admin_info["role"]),
                        "first_name": admin_info["first_name"],
                        "last_name": admin_info["last_name"],
                        "email": admin_info["email"],
                        "is_staff": admin_info["is_staff"],
                        "is_superuser": admin_info["is_superuser"],
                    },
                )
                user.set_password(demo_password)
                user.role = getattr(User.Role, admin_info["role"])
                user.is_staff = admin_info["is_staff"]
                user.is_superuser = admin_info["is_superuser"]
                if admin_info["username"] == "dean_engg":
                    user.school = school
                    school.dean = user
                    school.save(update_fields=["dean"])
                user.save()

            # 7. Seed Departments, Teachers, Courses, Batches, Subjects, and Students
            total_students_created = 0
            random_gen = random.Random(42)  # Deterministic seed for repeatable test verification

            for dept_info in DEPARTMENTS_DATA:
                dept, _ = Department.objects.get_or_create(
                    code=dept_info["code"],
                    defaults={
                        "name": dept_info["name"],
                        "school": school,
                    },
                )

                # HOD User
                hod_info = dept_info["hod"]
                hod_user, _ = User.objects.get_or_create(
                    username=hod_info["username"],
                    defaults={
                        "role": User.Role.HOD,
                        "first_name": hod_info["first_name"],
                        "last_name": hod_info["last_name"],
                        "email": hod_info["email"],
                        "is_staff": True,
                        "department": dept,
                        "school": school,
                    },
                )
                hod_user.set_password(demo_password)
                hod_user.department = dept
                hod_user.school = school
                hod_user.save()
                dept.hod = hod_user
                dept.save(update_fields=["hod"])

                # Teachers
                created_teachers = []
                for t_info in dept_info["teachers"]:
                    t_user, _ = User.objects.get_or_create(
                        username=t_info["username"],
                        defaults={
                            "role": User.Role.TEACHER,
                            "first_name": t_info["first_name"],
                            "last_name": t_info["last_name"],
                            "email": t_info["email"],
                            "is_staff": True,
                            "department": dept,
                            "school": school,
                        },
                    )
                    t_user.set_password(demo_password)
                    t_user.department = dept
                    t_user.school = school
                    t_user.save()

                    t_prof, _ = TeacherProfile.objects.get_or_create(
                        user=t_user,
                        defaults={
                            "staff_id": t_info["staff_id"],
                            "department": dept,
                            "designation": t_info["designation"],
                            "qualification": "Ph.D.",
                            "employment_type": "Permanent",
                        },
                    )
                    created_teachers.append(t_prof)

                # Course & Batch
                c_info = dept_info["course"]
                course, _ = Course.objects.get_or_create(
                    code=c_info["code"],
                    defaults={
                        "name": c_info["name"],
                        "level": c_info["level"],
                        "duration_years": c_info["duration_years"],
                        "department": dept,
                    },
                )

                batch, _ = Batch.objects.get_or_create(
                    batch_code=dept_info["batch_code"],
                    defaults={
                        "course": course,
                        "admission_year": 2024,
                        "current_study_year": 1,
                        "current_semester": 1,
                        "strength": len(dept_info["first_names"]),
                    },
                )

                # Subjects & Teaching Assignments
                dept_subjects = []
                for idx, s_info in enumerate(dept_info["subjects"]):
                    subject, _ = Subject.objects.get_or_create(
                        code=s_info["code"],
                        defaults={
                            "title": s_info["title"],
                            "course": course,
                            "semester": 1,
                            "credits": s_info["credits"],
                            "max_marks": s_info["max_marks"],
                            "internal_max": 30,
                            "external_max": 70,
                        },
                    )
                    dept_subjects.append(subject)

                    teacher_assigned = created_teachers[idx % len(created_teachers)]
                    TeachingAssignment.objects.get_or_create(
                        subject=subject,
                        batch=batch,
                        defaults={
                            "teacher": teacher_assigned,
                            "academic_session": "2024-2025",
                        },
                    )

                # Students (20 per department)
                for idx, first_name in enumerate(dept_info["first_names"], start=1):
                    last_name = LAST_NAMES[(idx - 1) % len(LAST_NAMES)]
                    roll_no = f"{dept_info['roll_prefix']}{idx:03d}"
                    username = f"demo_{roll_no.lower()}"
                    email = f"{username}@apex.edu.test"

                    st_user, _ = User.objects.get_or_create(
                        username=username,
                        defaults={
                            "role": User.Role.STUDENT,
                            "first_name": first_name,
                            "last_name": last_name,
                            "email": email,
                            "is_staff": False,
                        },
                    )
                    st_user.set_password(demo_password)
                    st_user.save()

                    # Static ML features
                    st_profile, _ = StudentProfile.objects.update_or_create(
                        user=st_user,
                        defaults={
                            "roll_no": roll_no,
                            "registration_no": f"REG2024{dept_info['code']}{idx:03d}",
                            "batch": batch,
                            "course": course,
                            "admission_year": 2024,
                            "current_year": 1,
                            "current_semester": 1,
                            "admission_type": "Regular",
                            "expected_graduation_year": 2028,
                            "guardian_name": f"{random_gen.choice(['Mr.', 'Mrs.'])} {last_name}",
                            "guardian_relation": "Parent",
                            "guardian_phone": f"98{random_gen.randint(10000000, 99999999)}",
                            "distance_from_home": random_gen.choice(["Near", "Moderate", "Far"]),
                            "parental_education_level": random_gen.choice(["High School", "College", "Postgraduate"]),
                            "family_income": random_gen.choice(["Low", "Medium", "High"]),
                            "internet_access": random_gen.choice([True, True, True, False]),
                            "access_to_resources": random_gen.choice(["Low", "Medium", "High"]),
                            "learning_disabilities": random_gen.choice([False, False, False, False, True]),
                            "data_origin": "demo",
                        },
                    )
                    total_students_created += 1

                    # INDEPENDENT TELEMETRY GENERATION
                    # Marks and behavioral features are sampled independently with zero correlation
                    sem_attendance = round(random_gen.uniform(55.0, 98.0), 1)
                    sem_study_hours = round(random_gen.uniform(4.0, 36.0), 1)
                    sem_sleep_hours = round(random_gen.uniform(5.0, 8.5), 1)
                    sem_motivation = random_gen.choice(["Low", "Medium", "High"])
                    sem_tutoring = random_gen.randint(0, 5)
                    sem_extracurricular = random_gen.choice([True, False])
                    sem_physical = random_gen.randint(0, 6)

                    # Independent exam marks per subject
                    total_marks_secured = 0
                    total_max_marks = 0
                    total_credits = 0
                    total_credit_points = 0.0

                    for subj in dept_subjects:
                        # Marks sampled independently of study hours and attendance
                        int_marks = random_gen.randint(12, 28)
                        ext_marks = random_gen.randint(28, 65)
                        sub_total = int_marks + ext_marks
                        grade_point = round(min(10.0, max(0.0, sub_total / 10.0)), 1)
                        credit_point = round(grade_point * subj.credits, 1)

                        Result.objects.update_or_create(
                            student=st_profile,
                            subject=subj,
                            semester=1,
                            defaults={
                                "batch": batch,
                                "teacher": created_teachers[0],
                                "internal_marks": int_marks,
                                "external_marks": ext_marks,
                                "total_secured": sub_total,
                                "max_marks": subj.max_marks,
                                "credits": subj.credits,
                                "grade_points": grade_point,
                                "credit_points": credit_point,
                                "letter_grade": "A" if sub_total >= 80 else ("B" if sub_total >= 60 else "C"),
                                "exam_session": "Winter 2024",
                            },
                        )

                        total_marks_secured += sub_total
                        total_max_marks += subj.max_marks
                        total_credits += subj.credits
                        total_credit_points += credit_point

                    sgpa = round(total_credit_points / total_credits, 2) if total_credits else 0.0
                    percentage = round((total_marks_secured / total_max_marks) * 100, 1) if total_max_marks else 0.0

                    # Semester Result record
                    SemesterResult.objects.update_or_create(
                        student=st_profile,
                        semester=1,
                        defaults={
                            "total_max": total_max_marks,
                            "total_secured": total_marks_secured,
                            "total_credits": total_credits,
                            "total_credit_points": total_credit_points,
                            "percentage": percentage,
                            "sgpa": sgpa,
                            "result_status": "Pass" if sgpa >= 4.0 else "Fail",
                            "exam_session": "Winter 2024",
                            "is_published": True,
                            "attendance_percentage": sem_attendance,
                            "hours_studied_per_week": sem_study_hours,
                            "sleep_hours_per_night": sem_sleep_hours,
                            "motivation_level": sem_motivation,
                            "tutoring_sessions": sem_tutoring,
                            "extracurricular_activities": sem_extracurricular,
                            "physical_activity": sem_physical,
                        },
                    )

                    # Continuous Assessment
                    for subj in dept_subjects[:2]:
                        InternalAssessment.objects.get_or_create(
                            student=st_profile,
                            subject=subj,
                            semester=1,
                            title="Midterm Examination 1",
                            defaults={
                                "batch": batch,
                                "teacher": created_teachers[0],
                                "assessment_type": "MIDTERM",
                                "marks_obtained": random_gen.randint(14, 24),
                                "max_marks": 25.0,
                                "is_submitted": True,
                            },
                        )

                    # Habit Preferences & Check-ins
                    StudentHabitPreference.objects.update_or_create(
                        student=st_profile,
                        defaults={
                            "frequency": "DAILY",
                            "streak_count": random_gen.randint(1, 14),
                        },
                    )

                    for day_offset in range(1, 4):
                        HabitCheckInLog.objects.get_or_create(
                            student=st_profile,
                            log_type="DAILY",
                            log_date=timezone_date_offset(day_offset),
                            defaults={
                                "hours_studied": round(random_gen.uniform(1.0, 5.0), 1),
                                "sleep_hours": round(random_gen.uniform(6.0, 8.0), 1),
                                "motivation_level": random_gen.choice(["Low", "Medium", "High"]),
                                "tutoring_sessions": 0,
                                "physical_activity": random_gen.choice([0, 1]),
                            },
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully seeded demo dataset: {total_students_created} students across 3 departments with data_origin='demo'."
                )
            )


def timezone_date_offset(days_ago):
    from django.utils import timezone
    from datetime import timedelta
    return timezone.now().date() - timedelta(days=days_ago)
