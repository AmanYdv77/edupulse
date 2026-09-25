"""
Views for student personal grade cards and staff scoped result rosters.
"""

from django.db.models import Avg, Count
from django.shortcuts import render

from accounts.permissions import role_required
from ..selectors import scoped_results_for, get_student_results_by_semester


@role_required("STUDENT")
def my_results(request):
    """The logged-in STUDENT's own results grouped by semester (restricted to published semesters)."""
    student = getattr(request.user, "student_profile", None)
    if student is None:
        return render(request, "my_results.html", {"no_profile": True})

    semester_list, has_results = get_student_results_by_semester(student)

    return render(request, "my_results.html", {
        "student": student,
        "semester_list": semester_list,
        "has_results": has_results,
    })


@role_required("TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN")
def scoped_results(request):
    """A results overview filtered to the logged-in user's organizational scope."""
    results, scope_label = scoped_results_for(request.user)

    students = (
        results.values(
            "student__roll_no",
            "student__user__first_name",
            "student__user__last_name",
            "student__course__department__name",
        )
        .annotate(subjects=Count("id"), avg_marks=Avg("total_secured"))
        .order_by("-avg_marks")
    )

    overall = results.aggregate(avg=Avg("total_secured"), total=Count("id"))

    return render(request, "scoped_results.html", {
        "user": request.user,
        "role_label": request.user.get_role_display(),
        "scope_label": scope_label,
        "students": students,
        "overall": overall,
        "student_count": len(students),
    })
