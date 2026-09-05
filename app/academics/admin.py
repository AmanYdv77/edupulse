from django.contrib import admin, messages
from .models import (University, School, Department, Course, Batch, Subject,
                     TeacherProfile, StudentProfile, TeachingAssignment,
                     Result, SemesterResult, InternalAssessment,
                     StudentHabitPreference, HabitCheckInLog)


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
    list_display = ("student", "semester", "percentage", "sgpa", "result_status", "is_published")
    list_filter = ("is_published", "semester", "result_status")
    search_fields = ("student__roll_no",)
    actions = ["publish_final_results", "revert_to_draft"]

    @admin.action(description="🚀 Publish Final Results (Make Live for Students)")
    def publish_final_results(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(
            request,
            f"Successfully published {updated} semester result record(s). Official results are now LIVE.",
            messages.SUCCESS
        )

    @admin.action(description="🔒 Revert to Draft (Hide from Students)")
    def revert_to_draft(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(
            request,
            f"Reverted {updated} semester result record(s) to draft status.",
            messages.WARNING
        )


@admin.register(InternalAssessment)
class InternalAssessmentAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "title", "assessment_type", "marks_obtained", "max_marks", "percentage", "teacher", "is_submitted", "date_conducted")
    list_filter = ("assessment_type", "is_submitted", "semester")
    search_fields = ("student__roll_no", "subject__code", "title")
    actions = ["mark_as_submitted", "mark_as_draft"]

    @admin.action(description="Publish Selected Assessments to Department")
    def mark_as_submitted(self, request, queryset):
        updated = queryset.update(is_submitted=True)
        self.message_user(request, f"{updated} assessment(s) marked as submitted and live in department hierarchy.", messages.SUCCESS)

    @admin.action(description="Revert Selected Assessments to Draft")
    def mark_as_draft(self, request, queryset):
        updated = queryset.update(is_submitted=False)
        self.message_user(request, f"{updated} assessment(s) reverted to draft.", messages.INFO)


@admin.register(StudentHabitPreference)
class StudentHabitPreferenceAdmin(admin.ModelAdmin):
    list_display = ("student", "frequency", "streak_count", "last_checkin_date")
    list_filter = ("frequency",)


@admin.register(HabitCheckInLog)
class HabitCheckInLogAdmin(admin.ModelAdmin):
    list_display = ("student", "log_type", "log_date", "hours_studied", "sleep_hours", "motivation_level")
    list_filter = ("log_type", "motivation_level", "log_date")
    search_fields = ("student__roll_no",)

