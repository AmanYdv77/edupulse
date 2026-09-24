"""
Model factories and synthetic data generation for EduPulse test suite.
Uses factory_boy and Faker. Enforces independent behavioral telemetry to prevent ML target leakage.
"""
import random
import factory
from django.contrib.auth import get_user_model
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
    HabitCheckInLog,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# USER FACTORIES
# ---------------------------------------------------------------------------

class UserFactory(factory.django.DjangoModelFactory):
    """Base user factory with unusable password and @example.test email domain."""

    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.test")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    role = User.Role.STUDENT
    status = "active"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = super()._create(model_class, *args, **kwargs)
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return user


class StudentUserFactory(UserFactory):
    role = User.Role.STUDENT


class TeacherUserFactory(UserFactory):
    role = User.Role.TEACHER


class HODUserFactory(UserFactory):
    role = User.Role.HOD


class DeanUserFactory(UserFactory):
    role = User.Role.DEAN


class VCUserFactory(UserFactory):
    role = User.Role.VC


class RegistrarUserFactory(UserFactory):
    role = User.Role.REGISTRAR


class ControllerUserFactory(UserFactory):
    role = User.Role.CONTROLLER


class AdminUserFactory(UserFactory):
    role = User.Role.SYSADMIN
    is_staff = True
    is_superuser = True


# ---------------------------------------------------------------------------
# ACADEMIC STRUCTURE FACTORIES
# ---------------------------------------------------------------------------

class UniversityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = University
        django_get_or_create = ("code",)

    name = factory.Sequence(lambda n: f"University {n}")
    code = factory.Sequence(lambda n: f"UNIV{n:03d}")
    established_year = 1995


class SchoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = School
        django_get_or_create = ("code",)

    name = factory.Sequence(lambda n: f"School of Engineering {n}")
    code = factory.Sequence(lambda n: f"SOE{n:03d}")
    university = factory.SubFactory(UniversityFactory)
    dean = factory.SubFactory(DeanUserFactory)


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ("code",)

    name = factory.Sequence(lambda n: f"Department of Computer Science {n}")
    code = factory.Sequence(lambda n: f"CSE{n:03d}")
    school = factory.SubFactory(SchoolFactory)
    hod = factory.SubFactory(HODUserFactory)


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course
        django_get_or_create = ("code",)

    name = factory.Sequence(lambda n: f"B.Tech Computer Science {n}")
    code = factory.Sequence(lambda n: f"BTCSE{n:03d}")
    level = "UG"
    duration_years = 4
    department = factory.SubFactory(DepartmentFactory)


class BatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Batch
        django_get_or_create = ("batch_code",)

    batch_code = factory.Sequence(lambda n: f"BTCSE-2024-{n:04d}")
    course = factory.SubFactory(CourseFactory)
    admission_year = 2024
    current_study_year = 1
    current_semester = 1
    strength = 60


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    code = factory.Sequence(lambda n: f"CS{100 + n}")
    title = factory.Sequence(lambda n: f"Core Computer Science {n}")
    course = factory.SubFactory(CourseFactory)
    semester = 1
    subject_type = "Theory"
    max_marks = 100
    internal_max = 30
    external_max = 70
    credits = 4


# ---------------------------------------------------------------------------
# PEOPLE PROFILE FACTORIES
# ---------------------------------------------------------------------------

class TeacherProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeacherProfile
        django_get_or_create = ("staff_id",)

    user = factory.SubFactory(TeacherUserFactory)
    staff_id = factory.Sequence(lambda n: f"FAC{n:04d}")
    department = factory.SubFactory(DepartmentFactory)
    designation = "Assistant Professor"
    qualification = "Ph.D."
    employment_type = "Permanent"
    specialization = "Artificial Intelligence"


class StudentProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StudentProfile
        django_get_or_create = ("roll_no",)

    user = factory.SubFactory(StudentUserFactory)
    roll_no = factory.Sequence(lambda n: f"24BTCSE{n:04d}")
    registration_no = factory.Sequence(lambda n: f"REG{n:06d}")
    batch = factory.SubFactory(BatchFactory)
    course = factory.LazyAttribute(lambda o: o.batch.course if o.batch else None)
    admission_year = 2024
    current_year = 1
    current_semester = 1
    admission_type = "Regular"
    expected_graduation_year = 2028
    guardian_name = factory.Faker("name")
    guardian_relation = "Parent"
    guardian_phone = "9876543210"

    # ML Static Features (from Kaggle Dataset schema)
    distance_from_home = "Near"
    parental_education_level = "College"
    family_income = "Medium"
    internet_access = True
    access_to_resources = "Medium"
    learning_disabilities = False


class TeachingAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeachingAssignment

    subject = factory.SubFactory(SubjectFactory)
    batch = factory.SubFactory(BatchFactory)
    teacher = factory.SubFactory(TeacherProfileFactory)
    academic_session = "2024-2025"


class ResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Result

    student = factory.SubFactory(StudentProfileFactory)
    subject = factory.SubFactory(SubjectFactory)
    batch = factory.LazyAttribute(lambda o: o.student.batch)
    teacher = factory.SubFactory(TeacherProfileFactory)
    semester = factory.LazyAttribute(lambda o: o.subject.semester)
    internal_marks = 25
    external_marks = 55
    total_secured = 80
    max_marks = 100
    credits = 4
    grade_points = 8.0
    credit_points = 32.0
    letter_grade = "A"
    exam_session = "Nov-Dec 2024"


# ---------------------------------------------------------------------------
# SEMESTER RESULT & TELEMETRY FACTORIES (ANTI-LEAKAGE DESIGN)
# ---------------------------------------------------------------------------
#
# ANTI-LEAKAGE RATIONALE:
# Behavioral telemetry (attendance_percentage, hours_studied_per_week, sleep_hours_per_night,
# motivation_level, tutoring_sessions, physical_activity, etc.) MUST be generated completely
# independently from marks, grade points, or SGPA in test factories.
#
# Real-world student telemetry is collected continually prior to or during the semester without
# prior knowledge of final examination results. If factories synthesized behavioral metrics as a
# direct mathematical function of SGPA or marks, unit and ML evaluation tests would be trained on
# or evaluated against artificial target leakage, falsifying model validation benchmarks.
# ---------------------------------------------------------------------------

class SemesterResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SemesterResult

    student = factory.SubFactory(StudentProfileFactory)
    semester = 1
    total_max = 500
    total_secured = 400
    total_credits = 20
    total_credit_points = 160.0
    percentage = 80.0
    sgpa = 8.0
    result_status = "PASS"
    is_published = True

    # Independent Behavioral Telemetry (Anti-Leakage)
    attendance_percentage = factory.LazyFunction(lambda: round(random.uniform(65.0, 98.0), 1))
    hours_studied_per_week = factory.LazyFunction(lambda: round(random.uniform(5.0, 35.0), 1))
    sleep_hours_per_night = factory.LazyFunction(lambda: round(random.uniform(5.0, 9.0), 1))
    motivation_level = factory.Iterator(["Low", "Medium", "High"])
    tutoring_sessions = factory.LazyFunction(lambda: random.randint(0, 5))
    extracurricular_activities = factory.Iterator([True, False])
    physical_activity = factory.LazyFunction(lambda: random.randint(0, 6))
    parental_involvement = factory.Iterator(["Low", "Medium", "High"])
    peer_influence = factory.Iterator(["Neutral", "Positive", "Negative"])


class HabitCheckInLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HabitCheckInLog

    student = factory.SubFactory(StudentProfileFactory)
    log_type = "DAILY"
    hours_studied = factory.LazyFunction(lambda: round(random.uniform(1.0, 5.0), 1))
    sleep_hours = factory.LazyFunction(lambda: round(random.uniform(6.0, 8.5), 1))
    motivation_level = factory.Iterator(["Low", "Medium", "High"])
    tutoring_sessions = 0
    physical_activity = 1


# ---------------------------------------------------------------------------
# HIERARCHY HELPER
# ---------------------------------------------------------------------------

import itertools

_univ_counter = itertools.count(1000)


def make_university(students_per_batch: int = 10) -> dict:
    """
    Construct a complete, connected university hierarchy for testing.
    Creates:
    - 1 University
    - 4 Executive users (VC, Registrar, Controller of Exams, SysAdmin)
    - 1 School with Dean
    - 1 Department with HOD
    - 1 Course and 1 Batch
    - 2 Subjects and 2 Teachers with TeachingAssignments
    - `students_per_batch` Students with Profiles, SemesterResults, Subject Results, and Habit Logs
    """
    univ_suffix = next(_univ_counter)
    university = UniversityFactory(
        name=f"Apex Institute of Technology {univ_suffix}",
        code=f"AIT{univ_suffix}",
    )


    vc = VCUserFactory(username=f"vc_apex_{univ_suffix}")
    registrar = RegistrarUserFactory(username=f"registrar_apex_{univ_suffix}")
    controller = ControllerUserFactory(username=f"coe_apex_{univ_suffix}")
    admin = AdminUserFactory(username=f"admin_apex_{univ_suffix}")

    dean = DeanUserFactory(username=f"dean_eng_{univ_suffix}")
    school = SchoolFactory(
        name=f"School of Engineering {univ_suffix}",
        code=f"SOE{univ_suffix}",
        university=university,
        dean=dean,
    )
    dean.school = school
    dean.save(update_fields=["school"])

    hod = HODUserFactory(username=f"hod_cse_{univ_suffix}", school=school)
    department = DepartmentFactory(
        name=f"Computer Science & Engineering {univ_suffix}",
        code=f"CSE{univ_suffix}",
        school=school,
        hod=hod,
    )
    hod.department = department
    hod.save(update_fields=["department"])

    course = CourseFactory(
        name=f"B.Tech Computer Science {univ_suffix}",
        code=f"BTCSE{univ_suffix}",
        level="UG",
        duration_years=4,
        department=department,
    )

    batch = BatchFactory(
        batch_code=f"BTCSE-2024-{univ_suffix}",
        course=course,
        admission_year=2024,
        current_study_year=1,
        current_semester=1,
        strength=students_per_batch,
    )

    sub1 = SubjectFactory(course=course, code=f"CS101_{univ_suffix}", title="Programming Fundamentals", semester=1)
    sub2 = SubjectFactory(course=course, code=f"MA101_{univ_suffix}", title="Engineering Mathematics I", semester=1)

    t1_user = TeacherUserFactory(username=f"teacher_alpha_{univ_suffix}", department=department, school=school)
    teacher1 = TeacherProfileFactory(user=t1_user, department=department, staff_id=f"FAC1_{univ_suffix}")

    t2_user = TeacherUserFactory(username=f"teacher_beta_{univ_suffix}", department=department, school=school)
    teacher2 = TeacherProfileFactory(user=t2_user, department=department, staff_id=f"FAC2_{univ_suffix}")

    assign1 = TeachingAssignmentFactory(subject=sub1, batch=batch, teacher=teacher1)
    assign2 = TeachingAssignmentFactory(subject=sub2, batch=batch, teacher=teacher2)

    students = []
    for i in range(students_per_batch):
        roll = f"24CSE{univ_suffix}{i+1:03d}"
        s_user = StudentUserFactory(
            username=f"stu_{univ_suffix}_{i+1:03d}",
            department=department,
            school=school,
        )
        student = StudentProfileFactory(
            user=s_user,
            roll_no=roll,
            batch=batch,
            course=course,
            admission_year=2024,
            current_year=1,
            current_semester=1,
        )
        SemesterResultFactory(student=student, semester=1)
        ResultFactory(student=student, subject=sub1, batch=batch, teacher=teacher1, semester=1)
        ResultFactory(student=student, subject=sub2, batch=batch, teacher=teacher2, semester=1)
        HabitCheckInLogFactory(student=student)
        students.append(student)

    return {
        "university": university,
        "executives": {
            "vc": vc,
            "registrar": registrar,
            "controller": controller,
            "admin": admin,
        },
        "school": school,
        "dean": dean,
        "department": department,
        "hod": hod,
        "course": course,
        "batch": batch,
        "subjects": [sub1, sub2],
        "teachers": [teacher1, teacher2],
        "assignments": [assign1, assign2],
        "students": students,
    }
