"""
Milestone 4 + 5 — seed REAL academic data with enough variety to SEE the
hierarchy work (different roles see different slices).

Run with:  python manage.py shell -c "exec(open('seed_academics.py').read())"

Creates:
  School of Engineering
    - CSE dept: B.Tech course, several students with results
    - ECE dept: B.Tech course, a student with results
  Assigns scope to staff:
    - hod_cse  -> HOD of CSE department
    - dean_engg-> Dean of School of Engineering
    - teacher_cse -> teaches in CSE
Safe to re-run.
"""
import random
from accounts.models import User
from academics.models import (School, Department, Course, Batch, Subject,
                              TeacherProfile, StudentProfile, Result)

random.seed(42)
print("\nSeeding academic data (Milestone 4+5)...")

# ---------------- Structure ----------------
school, _ = School.objects.get_or_create(code="ENGG", defaults={"name": "School of Engineering"})

cse, _ = Department.objects.get_or_create(code="CSE",
            defaults={"name": "Computer Science & Engineering", "school": school})
ece, _ = Department.objects.get_or_create(code="ECE",
            defaults={"name": "Electronics & Communication", "school": school})

cse_course, _ = Course.objects.get_or_create(code="CSE-UG",
            defaults={"name": "B.Tech CSE", "level": "UG", "duration_years": 4, "department": cse})
ece_course, _ = Course.objects.get_or_create(code="ECE-UG",
            defaults={"name": "B.Tech ECE", "level": "UG", "duration_years": 4, "department": ece})

cse_batch, _ = Batch.objects.get_or_create(batch_code="2023-CSE-UG",
            defaults={"course": cse_course, "admission_year": 2023, "current_semester": 4})
ece_batch, _ = Batch.objects.get_or_create(batch_code="2023-ECE-UG",
            defaults={"course": ece_course, "admission_year": 2023, "current_semester": 4})

# ---------------- Staff scope ----------------
# HOD of CSE
hod = User.objects.get(username="hod_cse")
hod.department = cse; hod.school = school; hod.save()
# Dean of Engineering
dean = User.objects.get(username="dean_engg")
dean.school = school; dean.save()
# Teacher in CSE
teacher_user = User.objects.get(username="teacher_cse")
teacher_user.department = cse; teacher_user.school = school; teacher_user.save()
teacher, _ = TeacherProfile.objects.get_or_create(user=teacher_user,
            defaults={"staff_id": "ADU-FAC-001", "department": cse,
                      "designation": "Assistant Professor"})

# A second teacher for ECE (create a user if missing)
ece_teacher_user, created = User.objects.get_or_create(username="teacher_ece",
            defaults={"role": User.Role.TEACHER, "first_name": "Anika", "last_name": "Menon",
                      "email": "teacher_ece@adu.edu.in", "is_staff": True})
if created:
    ece_teacher_user.set_password("Pass@123")
ece_teacher_user.department = ece; ece_teacher_user.school = school; ece_teacher_user.save()
ece_teacher, _ = TeacherProfile.objects.get_or_create(user=ece_teacher_user,
            defaults={"staff_id": "ADU-FAC-002", "department": ece,
                      "designation": "Assistant Professor"})

# ---------------- Subjects ----------------
def make_subjects(course, prefix):
    specs = [
        (1, f"U{prefix}101", "Mathematics I"),
        (1, f"U{prefix}102", "Programming Fundamentals"),
        (2, f"U{prefix}201", "Data Structures" if prefix == "CSE" else "Network Theory"),
        (2, f"U{prefix}202", "Discrete Mathematics" if prefix == "CSE" else "Signals & Systems"),
        (3, f"U{prefix}301", "Algorithms" if prefix == "CSE" else "Digital Electronics"),
        (3, f"U{prefix}302", "Database Systems" if prefix == "CSE" else "Microprocessors"),
    ]
    subs = {}
    for sem, code, title in specs:
        s, _ = Subject.objects.get_or_create(code=code, course=course,
            defaults={"title": title, "semester": sem, "max_marks": 100,
                      "subject_type": "Theory", "credits": 4})
        subs[code] = s
    return specs, subs

cse_specs, cse_subs = make_subjects(cse_course, "CSE")
ece_specs, ece_subs = make_subjects(ece_course, "ECE")

def grade(pct):
    if pct >= 90: return "O", 10.0
    if pct >= 80: return "A+", 9.0
    if pct >= 70: return "A", 8.0
    if pct >= 60: return "B+", 7.0
    if pct >= 55: return "B", 6.0
    if pct >= 50: return "C", 5.0
    if pct >= 40: return "P", 4.0
    return "F", 0.0

def add_results(student, specs, subs, teacher, ability):
    for sem, code, title in specs:
        subject = subs[code]
        secured = max(35, min(98, int(random.gauss(62 + ability, 9))))
        pct = secured
        lg, gp = grade(pct)
        internal = round(secured * 0.3); external = secured - internal
        Result.objects.update_or_create(
            student=student, subject=subject, semester=sem,
            defaults={"teacher": teacher, "internal_marks": internal,
                      "external_marks": external, "total_secured": secured,
                      "max_marks": 100, "credits": 4, "grade_points": gp,
                      "letter_grade": lg, "exam_session": f"SEM {sem}"})

# ---------------- Students ----------------
# Existing CSE student (Nisha = student_cs)
nisha = User.objects.get(username="student_cs")
nisha_profile, _ = StudentProfile.objects.get_or_create(user=nisha,
            defaults={"roll_no": "23-ENGG-CSE-UG-001", "batch": cse_batch,
                      "course": cse_course, "admission_year": 2023, "current_semester": 4})
add_results(nisha_profile, cse_specs, cse_subs, teacher, ability=8)

# A few more CSE students (so HOD/teacher see more than one)
extra_cse = [("ravi_cs", "Ravi", "Kumar", 0), ("meena_cs", "Meena", "Iyer", -5)]
for uname, fn, ln, ab in extra_cse:
    u, c = User.objects.get_or_create(username=uname,
            defaults={"role": User.Role.STUDENT, "first_name": fn, "last_name": ln,
                      "email": f"{uname}@student.adu.edu.in"})
    if c: u.set_password("Pass@123"); u.save()
    sp, _ = StudentProfile.objects.get_or_create(user=u,
            defaults={"roll_no": f"23-ENGG-CSE-UG-{random.randint(2,49):03d}",
                      "batch": cse_batch, "course": cse_course,
                      "admission_year": 2023, "current_semester": 4})
    add_results(sp, cse_specs, cse_subs, teacher, ab)

# An ECE student (so Dean sees 2 departments, but HOD-CSE does NOT see this one)
u, c = User.objects.get_or_create(username="arjun_ec",
        defaults={"role": User.Role.STUDENT, "first_name": "Arjun", "last_name": "Rao",
                  "email": "arjun_ec@student.adu.edu.in"})
if c: u.set_password("Pass@123"); u.save()
arjun = StudentProfile.objects.get_or_create(user=u,
        defaults={"roll_no": "23-ENGG-ECE-UG-001", "batch": ece_batch,
                  "course": ece_course, "admission_year": 2023, "current_semester": 4})[0]
add_results(arjun, ece_specs, ece_subs, ece_teacher, ability=3)

# ---------------- Summary ----------------
print(f"  Schools: {School.objects.count()} | Departments: {Department.objects.count()}")
print(f"  Students: {StudentProfile.objects.count()} | Results: {Result.objects.count()}")
print(f"  CSE results: {Result.objects.filter(subject__course=cse_course).count()}"
      f" | ECE results: {Result.objects.filter(subject__course=ece_course).count()}")
print("Done.")
