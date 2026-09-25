"""
Role and scope permission decorators and scope evaluation helpers for EduPulse.

Enforces default-deny access control across all analytical and administrative views.
Denied requests are logged at WARNING level with user id, role, and path only (no PII).
"""

import logging
from functools import wraps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from academics.models import (
    School,
    Department,
    Course,
    Batch,
    Result,
    TeachingAssignment,
)

logger = logging.getLogger("accounts.security")


def role_required(*allowed_roles):
    """
    Decorator for views checking that the user is authenticated and has one of the allowed roles.
    If unauthenticated, redirects to login.
    If authenticated but role not allowed, logs WARNING and raises PermissionDenied (HTTP 403).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

            user_role = getattr(request.user, "role", None)
            if user_role not in allowed_roles:
                logger.warning(
                    "Access denied: user_id=%s, role=%s, path=%s",
                    request.user.id,
                    user_role,
                    request.path,
                )
                raise PermissionDenied("You do not have permission to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def scope_for(user):
    """
    Return the comprehensive scope context for THIS user.
    Encodes the academic organizational hierarchy.
    """
    role = getattr(user, "role", None)

    # 1. Executive / University-Wide Roles
    if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN"):
        return {
            "role": role,
            "is_university_wide": True,
            "school": getattr(user, "school", None),
            "department": getattr(user, "department", None),
            "teacher_profile": getattr(user, "teacher_profile", None),
            "allowed_schools": School.objects.all(),
            "allowed_departments": Department.objects.all(),
            "allowed_courses": Course.objects.all(),
            "allowed_batches": Batch.objects.all(),
            "results": Result.objects.all(),
            "scope_label": "Entire University",
        }

    # 2. Dean (School Scope)
    if role == "DEAN":
        school = getattr(user, "school", None)
        if school:
            depts = Department.objects.filter(school=school)
            courses = Course.objects.filter(department__school=school)
            batches = Batch.objects.filter(course__department__school=school)
            results = Result.objects.filter(subject__course__department__school=school)
            label = f"School: {school}"
        else:
            depts = Department.objects.none()
            courses = Course.objects.none()
            batches = Batch.objects.none()
            results = Result.objects.none()
            label = "Your School (Unassigned)"

        return {
            "role": role,
            "is_university_wide": False,
            "school": school,
            "department": None,
            "teacher_profile": getattr(user, "teacher_profile", None),
            "allowed_schools": School.objects.filter(id=school.id) if school else School.objects.none(),
            "allowed_departments": depts,
            "allowed_courses": courses,
            "allowed_batches": batches,
            "results": results,
            "scope_label": label,
        }

    # 3. HOD (Department Scope)
    if role == "HOD":
        dept = getattr(user, "department", None)
        if not dept and hasattr(user, "teacher_profile"):
            dept = getattr(user.teacher_profile, "department", None)

        if dept:
            courses = Course.objects.filter(department=dept)
            batches = Batch.objects.filter(course__department=dept)
            results = Result.objects.filter(subject__course__department=dept)
            label = f"Department: {dept}"
            schools = School.objects.filter(id=dept.school_id) if dept.school else School.objects.none()
        else:
            courses = Course.objects.none()
            batches = Batch.objects.none()
            results = Result.objects.none()
            label = "Your Department (Unassigned)"
            schools = School.objects.none()

        return {
            "role": role,
            "is_university_wide": False,
            "school": dept.school if dept else None,
            "department": dept,
            "teacher_profile": getattr(user, "teacher_profile", None),
            "allowed_schools": schools,
            "allowed_departments": Department.objects.filter(id=dept.id) if dept else Department.objects.none(),
            "allowed_courses": courses,
            "allowed_batches": batches,
            "results": results,
            "scope_label": label,
        }

    # 4. Teacher (Class / Batch Teaching Assignment Scope)
    if role == "TEACHER":
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            assignments = TeachingAssignment.objects.filter(teacher=teacher)
            batch_ids = assignments.values_list("batch_id", flat=True)
            batches = Batch.objects.filter(id__in=batch_ids)
            courses = Course.objects.filter(id__in=batches.values_list("course_id", flat=True))
            depts = Department.objects.filter(id__in=courses.values_list("department_id", flat=True))
            schools = School.objects.filter(id__in=depts.values_list("school_id", flat=True))
            results = Result.objects.filter(teacher=teacher)
            label = "Students you teach"
        else:
            batches = Batch.objects.none()
            courses = Course.objects.none()
            depts = Department.objects.none()
            schools = School.objects.none()
            results = Result.objects.none()
            label = "Students you teach"

        return {
            "role": role,
            "is_university_wide": False,
            "school": getattr(user, "school", None),
            "department": getattr(user, "department", None),
            "teacher_profile": teacher,
            "allowed_schools": schools,
            "allowed_departments": depts,
            "allowed_courses": courses,
            "allowed_batches": batches,
            "results": results,
            "scope_label": label,
        }

    # 5. Student (Personal Scope: zero bulk results access)
    if role == "STUDENT":
        return {
            "role": role,
            "is_university_wide": False,
            "school": None,
            "department": None,
            "teacher_profile": None,
            "allowed_schools": School.objects.none(),
            "allowed_departments": Department.objects.none(),
            "allowed_courses": Course.objects.none(),
            "allowed_batches": Batch.objects.none(),
            "results": Result.objects.none(),
            "scope_label": "No access",
        }

    return {
        "role": role,
        "is_university_wide": False,
        "school": None,
        "department": None,
        "teacher_profile": None,
        "allowed_schools": School.objects.none(),
        "allowed_departments": Department.objects.none(),
        "allowed_courses": Course.objects.none(),
        "allowed_batches": Batch.objects.none(),
        "results": Result.objects.none(),
        "scope_label": "No access",
    }


def is_in_scope(user, *, school=None, department=None, course=None, batch=None):
    """
    Check if the specified academic entities fall within the authorized scope of the given user.
    Returns True if permitted, False otherwise.
    """
    scope = scope_for(user)
    if scope["is_university_wide"]:
        return True

    role = scope["role"]

    if role == "DEAN":
        user_school = scope["school"]
        if not user_school:
            return False
        if school and school != user_school:
            return False
        if department and department.school != user_school:
            return False
        if course and course.department.school != user_school:
            return False
        if batch and batch.course.department.school != user_school:
            return False
        return True

    if role == "HOD":
        user_dept = scope["department"]
        if not user_dept:
            return False
        if school and user_dept.school and school != user_dept.school:
            return False
        if department and department != user_dept:
            return False
        if course and course.department != user_dept:
            return False
        if batch and batch.course.department != user_dept:
            return False
        return True

    if role == "TEACHER":
        teacher = scope["teacher_profile"]
        if not teacher:
            return False
        assignments = TeachingAssignment.objects.filter(teacher=teacher)
        if batch and not assignments.filter(batch=batch).exists():
            return False
        if course and not assignments.filter(batch__course=course).exists():
            return False
        if department and not assignments.filter(batch__course__department=department).exists():
            return False
        if school and not assignments.filter(batch__course__department__school=school).exists():
            return False
        return True

    return False


ROLE_CAPABILITIES: dict[str, list[str]] = {
    "STUDENT": [
        "view_own_results",
        "view_own_predictions",
        "submit_habit_checkin",
        "view_own_habits",
    ],
    "TEACHER": [
        "view_class_analytics",
        "enter_internal_marks",
        "export_class_roster",
        "view_teaching_assignments",
    ],
    "HOD": [
        "view_department_analytics",
        "view_at_risk_roster",
        "export_department_roster",
    ],
    "DEAN": [
        "view_school_analytics",
        "view_at_risk_roster",
        "export_school_roster",
    ],
    "VC": [
        "view_executive_analytics",
    ],
    "REGISTRAR": [
        "view_executive_analytics",
    ],
    "CONTROLLER_OF_EXAMS": [
        "view_executive_analytics",
    ],
    "SYSTEM_ADMIN": [
        "manage_models",
        "view_system_health",
        "access_admin",
    ],
}


def capabilities_for(user) -> list[str]:
    """
    Returns the exact list of capability token strings for the given user,
    governed strictly by docs/ROLES_AND_FEATURES.md.
    Unauthenticated or inactive users receive an empty list.
    """
    if not user or not user.is_authenticated or not getattr(user, "is_active", False):
        return []

    role = getattr(user, "role", None)
    return list(ROLE_CAPABILITIES.get(role, []))
