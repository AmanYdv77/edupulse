"""
Role-Specific Analytics View Controllers and JSON Query API.
Dispatches to tailored Monolith Dark analytics templates for Student, Teacher, HOD, Dean, and Executive.
Default-deny access control is enforced via role and scope guards.
"""
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

from academics.models import (
    StudentProfile, TeacherProfile, Department, School, Course, Batch, TeachingAssignment
)
from .engine import (
    compute_cohort_deep_dive, get_student_analytics, get_teacher_analytics,
    get_hod_analytics, get_dean_analytics, get_executive_analytics
)
from accounts.permissions import role_required, scope_for, is_in_scope


@role_required("STUDENT", "TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN")
def analytics_hub(request):
    """
    Central dispatcher routing each user to their specific analytical cockpit.
    Enforces strict role scoping without insecure fallback expansion.
    """
    user = request.user
    role = user.role

    # 1. STUDENT
    if role == "STUDENT":
        student = getattr(user, "student_profile", None)
        if not student:
            return redirect("home")
        data = get_student_analytics(student)
        return render(request, "analytics/student_analytics.html", {
            **data,
            "role": role,
            "role_label": user.get_role_display(),
        })

    # 2. TEACHER
    elif role == "TEACHER":
        teacher = getattr(user, "teacher_profile", None)
        assignment_id = request.GET.get("assignment")
        try:
            assignment_id = int(assignment_id) if assignment_id else None
        except ValueError:
            assignment_id = None
        data = get_teacher_analytics(teacher, assignment_id=assignment_id)
        return render(request, "analytics/teacher_analytics.html", {
            **data,
            "role": role,
            "role_label": user.get_role_display(),
        })

    # 3. HOD
    elif role == "HOD":
        dept = user.department or (user.teacher_profile.department if hasattr(user, "teacher_profile") else None)
        if not dept:
            # Safe unassigned state: HTTP 200 with zero leaked data from other departments
            return render(request, "analytics/hod_analytics.html", {
                "department": None,
                "department_name": "No Department Assigned",
                "stats": {"total_students": 0, "pass_rate": 0, "avg_sgpa": 0, "at_risk": 0},
                "role": role,
                "role_label": user.get_role_display(),
                "unassigned": True,
                "courses": [],
                "batches": [],
                "distribution_labels": [],
                "distribution_data": [],
            })

        course_id = request.GET.get("course")
        batch_id = request.GET.get("batch")
        semester = request.GET.get("semester")
        try:
            course_id = int(course_id) if course_id else None
            batch_id = int(batch_id) if batch_id else None
            semester = int(semester) if semester else None
        except ValueError:
            course_id = batch_id = semester = None

        data = get_hod_analytics(dept, course_id=course_id, batch_id=batch_id, semester=semester)
        return render(request, "analytics/hod_analytics.html", {
            **data,
            "role": role,
            "role_label": user.get_role_display(),
        })

    # 4. DEAN
    elif role == "DEAN":
        school = user.school
        if not school:
            # Safe unassigned state: HTTP 200 with zero leaked data from other schools
            return render(request, "analytics/dean_analytics.html", {
                "school": None,
                "school_name": "No School Assigned",
                "stats": {"total_students": 0, "pass_rate": 0, "avg_sgpa": 0, "at_risk": 0},
                "role": role,
                "role_label": user.get_role_display(),
                "unassigned": True,
                "departments": [],
                "courses": [],
                "batches": [],
                "chart_labels": [],
                "chart_data": [],
            })

        dept_id = request.GET.get("dept")
        try:
            dept_id = int(dept_id) if dept_id else None
        except ValueError:
            dept_id = None

        data = get_dean_analytics(school, dept_id=dept_id)
        return render(request, "analytics/dean_analytics.html", {
            **data,
            "role": role,
            "role_label": user.get_role_display(),
        })

    # 5. VC, REGISTRAR, CONTROLLER OF EXAMS, SYSTEM ADMIN
    else:
        school_id = request.GET.get("school")
        try:
            school_id = int(school_id) if school_id else None
        except ValueError:
            school_id = None

        data = get_executive_analytics(school_id=school_id)
        return render(request, "analytics/executive_analytics.html", {
            **data,
            "role": role,
            "role_label": user.get_role_display(),
        })


# Re-export DRF API Views for the versioned analytics API family
from .api_views import (
    AnalyticsOverviewAPIView,
    AnalyticsBreakdownAPIView,
    AnalyticsTrendAPIView,
    AnalyticsDistributionAPIView,
    AtRiskRosterAPIView,
    AtRiskExportCSVAPIView,
)

