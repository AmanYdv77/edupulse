"""
Academic models representing university structure, courses, grades, teaching assignments,
and student habit telemetry.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# STRUCTURE
# ---------------------------------------------------------------------------

class University(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10, unique=True)
    established_year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=10, unique=True)
    university = models.ForeignKey(University, on_delete=models.CASCADE,
                                   null=True, blank=True, related_name="schools")
    dean = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="dean_of")

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=10, unique=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="departments")
    hod = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                            null=True, blank=True, related_name="hod_of")

    def __str__(self):
        return self.name


class Course(models.Model):
    LEVEL_CHOICES = [("UG", "Undergraduate"), ("PG", "Postgraduate")]
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, default="UG")
    duration_years = models.IntegerField(default=4)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="courses")

    def __str__(self):
        return f"{self.name} ({self.code})"


class Batch(models.Model):
    batch_code = models.CharField(max_length=30, unique=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="batches")
    admission_year = models.IntegerField()
    current_study_year = models.IntegerField(default=1)
    current_semester = models.IntegerField(default=1)
    strength = models.IntegerField(default=0)

    def __str__(self):
        return self.batch_code


class Subject(models.Model):
    SUBJECT_TYPES = [("Theory", "Theory"), ("Lab", "Lab")]
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=150)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="subjects")
    semester = models.IntegerField()
    subject_type = models.CharField(max_length=10, choices=SUBJECT_TYPES, default="Theory")
    max_marks = models.IntegerField(default=100)
    internal_max = models.IntegerField(default=30)
    external_max = models.IntegerField(default=70)
    credits = models.IntegerField(default=4)

    def __str__(self):
        return f"{self.code} — {self.title}"


# ---------------------------------------------------------------------------
# PEOPLE PROFILES
# ---------------------------------------------------------------------------

class TeacherProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="teacher_profile")
    staff_id = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="teachers")
    designation = models.CharField(max_length=80, blank=True)
    qualification = models.CharField(max_length=80, blank=True)
    employment_type = models.CharField(max_length=40, blank=True)
    specialization = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.staff_id})"


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="student_profile")
    roll_no = models.CharField(max_length=40, unique=True)
    registration_no = models.CharField(max_length=40, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="students")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="students")
    admission_year = models.IntegerField(null=True, blank=True)
    current_year = models.IntegerField(default=1)
    current_semester = models.IntegerField(default=1)
    admission_type = models.CharField(max_length=20, blank=True)
    expected_graduation_year = models.IntegerField(null=True, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_relation = models.CharField(max_length=40, blank=True)
    guardian_phone = models.CharField(max_length=15, blank=True)
    
    # ML Static Features (from Kaggle Dataset)
    distance_from_home = models.CharField(max_length=20, blank=True, null=True)
    parental_education_level = models.CharField(max_length=50, blank=True, null=True)
    family_income = models.CharField(max_length=20, blank=True, null=True)
    internet_access = models.BooleanField(default=True)
    access_to_resources = models.CharField(max_length=20, blank=True, null=True)
    learning_disabilities = models.BooleanField(default=False)

    DATA_ORIGIN_CHOICES = [("demo", "Demo"), ("real", "Real")]
    data_origin = models.CharField(
        max_length=10,
        choices=DATA_ORIGIN_CHOICES,
        default="real",
        db_index=True,
        help_text="Tracks whether student record is synthetic demo data or real institutional data."
    )

    @property
    def department(self):
        return self.course.department if self.course else None

    @property
    def school(self):
        return self.course.department.school if self.course and self.course.department else None

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.roll_no})"


# ---------------------------------------------------------------------------
# TEACHING ASSIGNMENTS (who teaches what to which batch)
# ---------------------------------------------------------------------------

class TeachingAssignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="assignments")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="assignments")
    academic_session = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.subject.code} -> {self.batch.batch_code}"


# ---------------------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------------------

class Result(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="results")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="results")
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="results")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="results")
    semester = models.IntegerField()
    internal_marks = models.IntegerField(default=0)
    external_marks = models.IntegerField(default=0)
    total_secured = models.IntegerField(default=0)
    max_marks = models.IntegerField(default=100)
    credits = models.IntegerField(default=4)
    grade_points = models.FloatField(default=0)
    credit_points = models.FloatField(default=0)
    letter_grade = models.CharField(max_length=2, blank=True)
    exam_session = models.CharField(max_length=30, blank=True)
    declaration_date = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ("student", "subject", "semester")

    @property
    def percentage(self):
        return round(self.total_secured / self.max_marks * 100, 1) if self.max_marks else 0

    def __str__(self):
        return f"{self.student.roll_no} | {self.subject.code} | {self.total_secured}/{self.max_marks}"


class SemesterResult(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE,
                                related_name="semester_results")
    semester = models.IntegerField()
    total_max = models.IntegerField(default=0)
    total_secured = models.IntegerField(default=0)
    total_credits = models.IntegerField(default=0)
    total_credit_points = models.FloatField(default=0)
    percentage = models.FloatField(default=0)
    sgpa = models.FloatField(default=0)
    result_status = models.CharField(max_length=10, blank=True)
    gc_no = models.CharField(max_length=20, blank=True)
    exam_session = models.CharField(max_length=30, blank=True)
    declaration_date = models.CharField(max_length=20, blank=True)
    is_published = models.BooleanField(
        default=True,
        help_text="Final official result published by Admin. When False, held as draft until bulk release."
    )

    # Behavioral / Habit Telemetry Fields (Official Institute Records or Left Blank)
    # NOTE (Task A16): These fields represent official recorded data at semester conclusion,
    # NOT self-reported daily logs. Missing values MUST remain None/NULL so that downstream
    # models and analysis do not train on invented defaults.
    attendance_percentage = models.FloatField(
        null=True, blank=True, default=None,
        help_text="Official attendance percentage recorded by the institution (0-100). None if unrecorded."
    )
    hours_studied_per_week = models.FloatField(
        null=True, blank=True, default=None,
        help_text="Official study hours per week. None if unrecorded."
    )
    sleep_hours_per_night = models.FloatField(
        null=True, blank=True, default=None,
        help_text="Official sleep hours per night. None if unrecorded."
    )
    motivation_level = models.CharField(
        max_length=20, blank=True, null=True, default=None,
        help_text="Official motivation level ('Low', 'Medium', 'High'). None if unrecorded."
    )
    tutoring_sessions = models.IntegerField(
        null=True, blank=True, default=None,
        help_text="Official count of tutoring sessions attended. None if unrecorded."
    )
    extracurricular_activities = models.BooleanField(
        null=True, blank=True, default=None,
        help_text="Official participation status in extracurricular activities. None if unrecorded."
    )
    physical_activity = models.IntegerField(
        null=True, blank=True, default=None,
        help_text="Official physical activity days/hours per week. None if unrecorded."
    )
    parental_involvement = models.CharField(
        max_length=20, blank=True, null=True, default=None,
        help_text="Official parental involvement level. None if unrecorded."
    )
    peer_influence = models.CharField(
        max_length=20, blank=True, null=True, default=None,
        help_text="Official peer influence level. None if unrecorded."
    )

    class Meta:
        unique_together = ("student", "semester")

    def __str__(self):
        return f"{self.student.roll_no} | Sem {self.semester} | SGPA {self.sgpa} | {'Published' if self.is_published else 'Draft'}"


# ---------------------------------------------------------------------------
# CONTINUOUS EVALUATION / INTERNAL ASSESSMENTS (Uploaded by Faculty)
# ---------------------------------------------------------------------------

class InternalAssessment(models.Model):
    ASSESSMENT_TYPES = [
        ("MIDTERM", "Mid-Semester Examination"),
        ("ASSIGNMENT", "Continuous Assignment"),
        ("QUIZ", "Class Test / Quiz"),
        ("LAB", "Practical / Lab Assessment"),
        ("PROJECT", "Term Project / Seminar"),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="internal_assessments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="internal_assessments")
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="internal_assessments")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="internal_assessments")
    semester = models.IntegerField(default=1)
    title = models.CharField(max_length=100, help_text="e.g. Midterm Test 1, Assignment 2")
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPES, default="ASSIGNMENT")
    marks_obtained = models.FloatField(default=0.0)
    max_marks = models.FloatField(default=25.0)
    date_conducted = models.DateField(default=timezone.now)
    is_submitted = models.BooleanField(default=True, help_text="Visible across hierarchical scope when submitted")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_conducted", "-created_at"]

    @property
    def percentage(self):
        return round((self.marks_obtained / self.max_marks) * 100, 1) if self.max_marks > 0 else 0.0

    def __str__(self):
        return f"{self.student.roll_no} | {self.subject.code} | {self.title}: {self.marks_obtained}/{self.max_marks}"


# ---------------------------------------------------------------------------
# HABIT TRACKING & DATA COLLECTION
# ---------------------------------------------------------------------------
from django.utils import timezone

class StudentHabitPreference(models.Model):
    FREQUENCY_CHOICES = [
        ("DAILY", "Daily Quick-Check (30 sec)"),
        ("WEEKLY", "Weekly Summary (2 min)"),
    ]
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name="habit_preference")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="DAILY")
    streak_count = models.IntegerField(default=0)
    last_checkin_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.roll_no} - {self.frequency} (Streak: {self.streak_count})"


class HabitCheckInLog(models.Model):
    LOG_TYPES = [
        ("DAILY", "Daily Log"),
        ("WEEKLY", "Weekly Log"),
    ]
    MOTIVATION_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="habit_logs")
    log_type = models.CharField(max_length=10, choices=LOG_TYPES, default="DAILY")
    log_date = models.DateField(default=timezone.now)
    hours_studied = models.FloatField(default=0.0, help_text="Hours studied (today if daily, total for week if weekly)")
    sleep_hours = models.FloatField(default=7.0, help_text="Hours slept (last night if daily, avg/night if weekly)")
    motivation_level = models.CharField(max_length=10, choices=MOTIVATION_CHOICES, default="Medium")
    tutoring_sessions = models.IntegerField(default=0, help_text="Tutoring sessions attended")
    physical_activity = models.IntegerField(default=0, help_text="Hours/days of physical activity or exercise")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-log_date", "-created_at"]

    def __str__(self):
        return f"{self.student.roll_no} | {self.log_type} on {self.log_date} | Study: {self.hours_studied}h, Sleep: {self.sleep_hours}h"


def sync_habits_to_semester_result(student):
    """
    Deprecated (Task A16).
    Self-reported habit logs must NOT overwrite official SemesterResult academic records.
    Use `academics.services.habits.habit_summary(student)` to query self-reported habit metrics.
    """
    import warnings
    warnings.warn(
        "sync_habits_to_semester_result is deprecated and no longer writes to SemesterResult. "
        "Use academics.services.habits.habit_summary(student) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
