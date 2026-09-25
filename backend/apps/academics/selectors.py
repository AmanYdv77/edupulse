"""
Query selectors for the academics domain.
Extracts complex database queries and aggregations out of view functions.
"""

from typing import Any, Tuple
from django.db.models import Avg, Count
from accounts.permissions import scope_for


def scoped_results_for(user: Any) -> Tuple[Any, str]:
    """
    Returns (results_queryset, scope_label) for what THIS user is allowed to see.
    Encodes the academic organizational hierarchy via permissions.scope_for.
    """
    scope = scope_for(user)
    return scope["results"], scope["scope_label"]


def get_student_results_by_semester(student: Any) -> Tuple[list[dict], bool]:
    """
    Retrieves and calculates semester-grouped results and SGPA for a student.
    Restricted to published semesters.
    """
    from academics.models import SemesterResult

    published_sems = set(
        SemesterResult.objects.filter(student=student, is_published=True).values_list("semester", flat=True)
    )

    results = (
        student.results.filter(semester__in=published_sems)
        .select_related("subject", "teacher__user")
        .order_by("semester", "subject__code")
    )

    semesters: dict[int, dict] = {}
    for r in results:
        s = semesters.setdefault(
            r.semester,
            {"rows": [], "total_secured": 0, "total_max": 0, "total_credit_points": 0.0, "total_credits": 0},
        )
        s["rows"].append(r)
        s["total_secured"] += r.total_secured
        s["total_max"] += r.max_marks
        s["total_credit_points"] += r.grade_points * r.credits
        s["total_credits"] += r.credits

    semester_list = []
    for sem in sorted(semesters):
        s = semesters[sem]
        pct = round(s["total_secured"] / s["total_max"] * 100, 1) if s["total_max"] else 0
        sgpa = round(s["total_credit_points"] / s["total_credits"], 2) if s["total_credits"] else 0
        semester_list.append({
            "semester": sem,
            "rows": s["rows"],
            "percentage": pct,
            "sgpa": sgpa,
            "status": "PASS" if pct >= 40 else "FAIL",
        })

    return semester_list, bool(semester_list)
