"""
Big Data Load — import the full 800-student dataset from university.db into Django.

Run with:
  python manage.py shell -c "exec(open('import_university_data.py').read())"

Requirements:
  * university.db must be in the SAME folder as this script (next to manage.py).

What it does:
  * Reads university.db (the rich sample dataset).
  * Creates University/School/Department/Course/Batch/Subject.
  * Creates User accounts for all staff + students (password = Pass@123).
  * Creates Teacher/Student profiles, teaching assignments, results, semester cards.
  * PRESERVES your existing superuser admin account.

Safe to re-run: it clears previously imported academic data first (but NOT your
superuser). Uses login_id/roll_no/codes to avoid duplicates.
"""
import os
import sqlite3
from django.db import transaction

from accounts.models import User
from academics.models import (University, School, Department, Course, Batch,
                              Subject, TeacherProfile, StudentProfile,
                              TeachingAssignment, Result, SemesterResult)

if "__file__" in globals():
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/university.db"))
else:
    DB_PATH = "../data/university.db"

DEFAULT_PASSWORD = "Pass@123"

if not os.path.exists(DB_PATH):
    print(f"ERROR: {DB_PATH} not found. Expected raw database at {DB_PATH}.")
else:
    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    s = src.cursor()

    print("\n=== Big Data Load: importing university.db ===")

    # Speed: hash the shared password ONCE, reuse for all imported users.
    # (Hashing 800+ passwords individually is the slow part; they're all the same.)
    from django.contrib.auth.hashers import make_password
    SHARED_HASH = make_password(DEFAULT_PASSWORD)

    with transaction.atomic():
        # ---- Clear previously imported academic data (keep superusers) ----
        print("Clearing old academic data...")
        SemesterResult.objects.all().delete()
        Result.objects.all().delete()
        TeachingAssignment.objects.all().delete()
        Subject.objects.all().delete()
        StudentProfile.objects.all().delete()
        TeacherProfile.objects.all().delete()
        Batch.objects.all().delete()
        Course.objects.all().delete()
        Department.objects.all().delete()
        School.objects.all().delete()
        University.objects.all().delete()
        # Remove non-superuser users (the imported ones); keep YOUR admin.
        User.objects.filter(is_superuser=False).delete()

        # ---- University ----
        u = s.execute("SELECT * FROM university LIMIT 1").fetchone()
        uni = University.objects.create(name=u["name"], code=u["code"],
                                        established_year=u["established_year"])

        # ---- Maps from old id -> new Django object ----
        school_map, dept_map, course_map, batch_map = {}, {}, {}, {}
        subject_map, user_map, teacher_map, student_map = {}, {}, {}, {}

        # ---- Schools ----
        for r in s.execute("SELECT * FROM schools"):
            school_map[r["id"]] = School.objects.create(
                name=r["name"], code=r["code"], university=uni)

        # ---- Departments ----
        for r in s.execute("SELECT * FROM departments"):
            dept_map[r["id"]] = Department.objects.create(
                name=r["name"], code=r["code"], school=school_map[r["school_id"]])

        # ---- Courses ----
        for r in s.execute("SELECT * FROM courses"):
            course_map[r["id"]] = Course.objects.create(
                name=r["name"], code=r["code"], level=r["level"],
                duration_years=r["duration_years"], department=dept_map[r["department_id"]])

        # ---- Batches ----
        for r in s.execute("SELECT * FROM batches"):
            batch_map[r["id"]] = Batch.objects.create(
                batch_code=r["batch_code"], course=course_map[r["course_id"]],
                admission_year=r["admission_year"], current_study_year=r["current_study_year"],
                current_semester=r["current_semester"], strength=r["strength"])

        # ---- Subjects ----
        for r in s.execute("SELECT * FROM subjects"):
            subject_map[r["id"]] = Subject.objects.create(
                code=r["code"], title=r["title"], course=course_map[r["course_id"]],
                semester=r["semester"], subject_type=r["subject_type"],
                max_marks=r["max_marks"], internal_max=r["internal_max"],
                external_max=r["external_max"], credits=r["credits"])

        # ---- Users (staff + students) ----
        print("Creating users (this is the big one)...")
        role_map = {"VC": "VC", "REGISTRAR": "REGISTRAR",
                    "CONTROLLER_OF_EXAMS": "CONTROLLER_OF_EXAMS",
                    "SYSTEM_ADMIN": "SYSTEM_ADMIN", "DEAN": "DEAN", "HOD": "HOD",
                    "TEACHER": "TEACHER", "STUDENT": "STUDENT"}
        new_users = []
        rows = s.execute("SELECT * FROM users").fetchall()
        for r in rows:
            parts = (r["full_name"] or "").split(" ", 1)
            first = parts[0]; last = parts[1] if len(parts) > 1 else ""
            user = User(
                username=r["login_id"], email=r["email"] or "",
                first_name=first, last_name=last,
                role=role_map.get(r["role"], "STUDENT"),
                phone=r["phone"] or "", dob=r["dob"] or "", gender=r["gender"] or "",
                blood_group=r["blood_group"] or "", address_city=r["address_city"] or "",
                address_state=r["address_state"] or "", category=r["category"] or "",
                status=r["status"] or "active",
                is_staff=(r["role"] != "STUDENT"),
                password=SHARED_HASH,   # reuse the pre-computed hash (fast!)
            )
            new_users.append((r["id"], r["school_id"], r["department_id"], user))

        # bulk create users for speed
        User.objects.bulk_create([nu[3] for nu in new_users], batch_size=200)
        # reload to get ids + set scope FKs
        created = {u.username: u for u in User.objects.filter(is_superuser=False)}
        for old_id, sch_id, dep_id, user in new_users:
            obj = created[user.username]
            obj.school = school_map.get(sch_id)
            obj.department = dept_map.get(dep_id)
            user_map[old_id] = obj
        User.objects.bulk_update(
            [user_map[o] for o, _, _, _ in new_users], ["school", "department"], batch_size=200)

        # ---- Staff profiles (teachers) ----
        for r in s.execute("SELECT * FROM staff_profiles"):
            owner = user_map.get(r["user_id"])
            if owner and owner.role == "TEACHER":
                teacher_map[r["user_id"]] = TeacherProfile.objects.create(
                    user=owner, staff_id=r["staff_id"], department=dept_map.get(r["department_id"]),
                    designation=r["designation"] or "", qualification=r["qualification"] or "",
                    employment_type=r["employment_type"] or "", specialization=r["specialization"] or "")

        # ---- Student profiles ----
        for r in s.execute("SELECT * FROM student_profiles"):
            owner = user_map.get(r["user_id"])
            if owner:
                student_map[r["id"]] = StudentProfile.objects.create(
                    user=owner, roll_no=r["roll_no"], registration_no=r["registration_no"] or "",
                    batch=batch_map.get(r["batch_id"]), course=course_map.get(r["course_id"]),
                    admission_year=r["admission_year"], current_year=r["current_year"],
                    current_semester=r["current_semester"], admission_type=r["admission_type"] or "",
                    expected_graduation_year=r["expected_graduation_year"],
                    guardian_name=r["guardian_name"] or "", guardian_relation=r["guardian_relation"] or "",
                    guardian_phone=r["guardian_phone"] or "")

        # ---- Teaching assignments ----
        for r in s.execute("SELECT * FROM teaching_assignments"):
            TeachingAssignment.objects.create(
                subject=subject_map.get(r["subject_id"]), batch=batch_map.get(r["batch_id"]),
                teacher=teacher_map.get(r["teacher_user_id"]),
                academic_session=r["academic_session"] or "")

        # ---- Results (bulk for speed) ----
        print("Importing results (15k rows, please wait)...")
        result_objs = []
        for r in s.execute("SELECT * FROM results"):
            stu = student_map.get(r["student_profile_id"])
            sub = subject_map.get(r["subject_id"])
            if stu and sub:
                result_objs.append(Result(
                    student=stu, subject=sub, batch=batch_map.get(r["batch_id"]),
                    teacher=teacher_map.get(r["teacher_user_id"]), semester=r["semester"],
                    internal_marks=r["internal_marks"], external_marks=r["external_marks"],
                    total_secured=r["total_secured"], max_marks=r["max_marks"],
                    credits=r["credits"], grade_points=r["grade_points"],
                    credit_points=r["credit_points"], letter_grade=r["letter_grade"] or "",
                    exam_session=r["exam_session"] or "", declaration_date=r["declaration_date"] or ""))
        Result.objects.bulk_create(result_objs, batch_size=500)

        # ---- Semester results ----
        sem_objs = []
        for r in s.execute("SELECT * FROM semester_results"):
            stu = student_map.get(r["student_profile_id"])
            if stu:
                sem_objs.append(SemesterResult(
                    student=stu, semester=r["semester"], total_max=r["total_max"],
                    total_secured=r["total_secured"], total_credits=r["total_credits"],
                    total_credit_points=r["total_credit_points"], percentage=r["percentage"],
                    sgpa=r["sgpa"], result_status=r["result_status"] or "",
                    gc_no=r["gc_no"] or "", exam_session=r["exam_session"] or "",
                    declaration_date=r["declaration_date"] or ""))
        SemesterResult.objects.bulk_create(sem_objs, batch_size=500)

        # link deans/hods to their school/department (best effort by code)
        for r in s.execute("SELECT * FROM schools"):
            if r["dean_user_id"] and r["dean_user_id"] in user_map:
                sc = school_map[r["id"]]; sc.dean = user_map[r["dean_user_id"]]; sc.save()
        for r in s.execute("SELECT * FROM departments"):
            if r["hod_user_id"] and r["hod_user_id"] in user_map:
                dp = dept_map[r["id"]]; dp.hod = user_map[r["hod_user_id"]]; dp.save()

    src.close()

    # ---- Summary ----
    print("\n=== Import complete ===")
    print(f"  Users:        {User.objects.count()}  (incl. your admin)")
    print(f"  Schools:      {School.objects.count()}")
    print(f"  Departments:  {Department.objects.count()}")
    print(f"  Courses:      {Course.objects.count()}")
    print(f"  Subjects:     {Subject.objects.count()}")
    print(f"  Students:     {StudentProfile.objects.count()}")
    print(f"  Teachers:     {TeacherProfile.objects.count()}")
    print(f"  Results:      {Result.objects.count()}")
    print(f"  Sem results:  {SemesterResult.objects.count()}")
    print("\n  All imported accounts use password: Pass@123")
    print("  Sample logins: vc | dean_engg | hod_cse | cse_fac01 | 25-engg-cse-ug-001")
