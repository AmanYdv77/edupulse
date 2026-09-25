"""
Views for faculty continuous evaluation and internal marks upload.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect

from accounts.permissions import role_required
from academics.models import TeachingAssignment, InternalAssessment
from ..services.marks import process_internal_marks_csv, process_internal_marks_form


@role_required("TEACHER", "SYSTEM_ADMIN")
def teacher_internal_marks(request):
    """Allows faculty to enter internal marks for assigned batches via web form or CSV."""
    teacher = getattr(request.user, "teacher_profile", None)
    if not teacher:
        raise PermissionDenied("Access restricted to active faculty members with a teacher profile.")

    assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related("subject", "batch", "batch__course")

    assignment_id = request.GET.get("assignment")
    selected_assignment = None
    if assignment_id:
        requested_assignment = TeachingAssignment.objects.filter(id=assignment_id).first()
        if not requested_assignment or requested_assignment.teacher != teacher:
            raise PermissionDenied("You do not have permission to view or manage this teaching assignment.")
        selected_assignment = requested_assignment
    elif assignments.exists():
        selected_assignment = assignments.first()

    students = selected_assignment.batch.students.select_related("user", "course").order_by("roll_no") if (selected_assignment and selected_assignment.batch) else []

    if request.method == "POST":
        if not selected_assignment:
            messages.error(request, "Please select an active teaching assignment first.")
            return redirect("teacher_internal_marks")

        if selected_assignment.teacher != teacher:
            raise PermissionDenied("You can only submit marks for your own assigned classes.")

        title = request.POST.get("title", "").strip() or "Continuous Assessment"
        assessment_type = request.POST.get("assessment_type", "ASSIGNMENT")
        try:
            max_marks = float(request.POST.get("max_marks") or 25.0)
        except ValueError:
            max_marks = 25.0
        semester = selected_assignment.batch.current_semester if selected_assignment.batch else 1

        csv_file = request.FILES.get("csv_file")
        if csv_file:
            saved_count, error = process_internal_marks_csv(selected_assignment, teacher, semester, title, assessment_type, max_marks, csv_file)
            if error:
                messages.error(request, f"Error parsing CSV file: {error}")
        else:
            saved_count = process_internal_marks_form(selected_assignment, teacher, semester, title, assessment_type, max_marks, students, request.POST)

        if saved_count > 0:
            messages.success(request, f"Successfully uploaded marks for {saved_count} student(s) in {selected_assignment.subject.code}! Records are now LIVE across the department hierarchy.")
        else:
            messages.warning(request, "No marks were recorded. Please ensure student marks are entered or the CSV is formatted properly.")

        redirect_url = f"/teacher/internal-marks/?assignment={selected_assignment.id}" if selected_assignment else "/teacher/internal-marks/"
        return redirect(redirect_url)

    recent_assessments = InternalAssessment.objects.filter(
        subject=selected_assignment.subject,
        batch=selected_assignment.batch
    ).order_by("-created_at")[:20] if selected_assignment else []

    return render(request, "teacher_internal_marks.html", {
        "teacher": teacher,
        "assignments": assignments,
        "selected_assignment": selected_assignment,
        "students": students,
        "recent_assessments": recent_assessments,
    })
