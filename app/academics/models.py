"""
Academic models — upgraded (Milestone 6: Big Data Load) to match the rich
university.db structure: full grade cards, credits, teaching assignments,
semester results. This is the production-grade shape.
"""
from django.conf import settings
from django.db import models


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

    # ML Dynamic/Behavioral Features (from Kaggle Dataset)
    attendance_percentage = models.FloatField(default=0)
    hours_studied_per_week = models.FloatField(default=0)
    sleep_hours_per_night = models.FloatField(default=0)
    motivation_level = models.CharField(max_length=20, blank=True, null=True)
    tutoring_sessions = models.IntegerField(default=0)
    extracurricular_activities = models.BooleanField(default=False)
    physical_activity = models.IntegerField(default=0)
    parental_involvement = models.CharField(max_length=20, blank=True, null=True)
    peer_influence = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        unique_together = ("student", "semester")

    def __str__(self):
        return f"{self.student.roll_no} | Sem {self.semester} | SGPA {self.sgpa}"
