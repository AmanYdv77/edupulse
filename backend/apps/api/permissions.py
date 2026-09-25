"""
REST API permission classes enforcing role-based and scope-based access control.
"""

from django.conf import settings
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import capabilities_for, scope_for
from academics.models import StudentProfile, TeachingAssignment


def has_capability(user, capability: str) -> bool:
    """Checks whether the user possesses the required capability token."""
    return capability in capabilities_for(user)


class HasCapabilityPermission(permissions.BasePermission):
    """
    Base permission checking if request.user has a specific capability.
    Subclasses define `required_capability`.
    """
    required_capability: str = ""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not self.required_capability:
            return True
        return has_capability(request.user, self.required_capability)


class IsStudentUser(permissions.BasePermission):
    """Allows access only to authenticated students."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "STUDENT"
            and hasattr(request.user, "student_profile")
        )


class IsTeacherUser(permissions.BasePermission):
    """Allows access only to authenticated teachers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "TEACHER"
            and hasattr(request.user, "teacher_profile")
        )


class IsSystemAdminUser(permissions.BasePermission):
    """Allows access only to authenticated system administrators."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "role", None) == "SYSTEM_ADMIN"
                or request.user.is_superuser
            )
        )


class IsSelfOrInStaffScope(permissions.BasePermission):
    """
    Object permission checking student identity / faculty scope:
    - Student: Can access ONLY their own record.
    - Teacher: Can access ONLY students in batches they currently teach.
    - HOD: Can access ONLY students in their assigned department.
    - Dean: Can access ONLY students in departments within their assigned school.
    - Executives (VC, Registrar, Controller): REFUSED (HTTP 403). Executives receive aggregates only.
    - System Admin: Allowed.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # obj is expected to be a Student instance
        if not isinstance(obj, StudentProfile):
            return False

        user = request.user
        role = getattr(user, "role", None)

        # 1. Student check: own record only
        if role == "STUDENT":
            student_profile = getattr(user, "student_profile", None)
            return bool(student_profile and student_profile.id == obj.id)

        # 2. Executive check: Executives see aggregates only; per-student rows are strictly forbidden
        if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS"):
            return False

        # 3. System Admin check
        if role == "SYSTEM_ADMIN" or user.is_superuser:
            return True

        # 4. Teacher check: student must be enrolled in a batch the teacher teaches
        if role == "TEACHER":
            teacher = getattr(user, "teacher_profile", None)
            if not teacher:
                return False
            # Check if student is in any batch taught by this teacher
            return TeachingAssignment.objects.filter(
                teacher=teacher,
                batch=obj.batch,
            ).exists()

        # 5. HOD check: student must be in HOD's department
        if role == "HOD":
            dept = getattr(user, "department", None)
            if not dept and hasattr(user, "teacher_profile"):
                dept = getattr(user.teacher_profile, "department", None)
            if not dept:
                return False
            return obj.department_id == dept.id

        # 6. Dean check: student's department must be within Dean's school
        if role == "DEAN":
            school = getattr(user, "school", None)
            if not school:
                return False
            if obj.department and obj.department.school_id == school.id:
                return True
            return False

        return False


class StaffOrDevOnly(permissions.BasePermission):
    """
    Allows Swagger UI documentation access:
    - In development (DEBUG=True): any authenticated or public user.
    - Outside development (DEBUG=False): staff and faculty roles only.
    """

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_staff
                or getattr(request.user, "role", None)
                in ("SYSTEM_ADMIN", "TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS")
            )
        )


class CanViewAnalytics(permissions.BasePermission):
    """
    Requires any of the analytical viewing capabilities:
    view_class_analytics, view_department_analytics, view_school_analytics, view_executive_analytics.
    Denies Students and System Admins.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_caps = set(capabilities_for(request.user))
        allowed_caps = {
            "view_class_analytics",
            "view_department_analytics",
            "view_school_analytics",
            "view_executive_analytics",
        }
        return bool(user_caps.intersection(allowed_caps))


class CanViewAtRiskRoster(permissions.BasePermission):
    """
    Requires view_at_risk_roster capability (Faculty only: HOD, Dean).
    Executives, Teachers, Students, and System Admins receive HTTP 403.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return has_capability(request.user, "view_at_risk_roster")


class CanExportAtRiskRoster(permissions.BasePermission):
    """
    Requires view_at_risk_roster AND either export_department_roster or export_school_roster.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_caps = set(capabilities_for(request.user))
        if "view_at_risk_roster" not in user_caps:
            return False
        return bool(user_caps.intersection({"export_department_roster", "export_school_roster"}))

