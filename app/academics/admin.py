"""Register academic models in the admin panel."""
from django.contrib import admin
from .models import (University, School, Department, Course, Batch, Subject,
                     TeacherProfile, StudentProfile, TeachingAssignment,
                     Result, SemesterResult)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "established_year")


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "university")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "school")
    list_filter = ("school",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "level", "department")
    list_filter = ("level", "department")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("batch_code", "course", "admission_year", "current_semester", "strength")
    list_filter = ("course",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "course", "semester", "subject_type", "credits")
    list_filter = ("course", "semester", "subject_type")
    search_fields = ("code", "title")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("staff_id", "user", "department", "designation")
    list_filter = ("department",)
    search_fields = ("staff_id", "user__first_name", "user__last_name")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("roll_no", "user", "course", "current_semester", "admission_year")
    list_filter = ("course", "admission_year", "current_semester")
    search_fields = ("roll_no", "registration_no", "user__first_name", "user__last_name")


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ("subject", "batch", "teacher", "academic_session")
    list_filter = ("academic_session",)
    search_fields = ("subject__code",)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "semester", "total_secured", "max_marks", "letter_grade", "teacher")
    list_filter = ("semester", "letter_grade", "subject__course")
    search_fields = ("student__roll_no", "subject__code")


@admin.register(SemesterResult)
class SemesterResultAdmin(admin.ModelAdmin):
    list_display = ("student", "semester", "percentage", "sgpa", "result_status")
    list_filter = ("semester", "result_status")
    search_fields = ("student__roll_no",)
