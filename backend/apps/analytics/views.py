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


@role_required("TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN")
@require_GET
def api_cohort_query(request):
    """
    JSON API for dynamic statistical drill-downs.
    Enforces strict role and scope authorization:
    - Students are denied access (HTTP 403).
    - Requests for out-of-scope academic entities return HTTP 403.
    - Teachers only see named students for batches they teach.
    """
    batch_id = request.GET.get("batch_id")
    course_id = request.GET.get("course_id")
    semester = request.GET.get("semester")
    department_id = request.GET.get("department_id")
    school_id = request.GET.get("school_id")

    batch = Batch.objects.filter(id=batch_id).first() if batch_id else None
    course = Course.objects.filter(id=course_id).first() if course_id else None
    department = Department.objects.filter(id=department_id).first() if department_id else None
    school = School.objects.filter(id=school_id).first() if school_id else None

    # Verify requested entities fall within the caller's authorized scope
    scope = scope_for(request.user)
    if not scope["is_university_wide"]:
        if school and not scope["allowed_schools"].filter(id=school.id).exists():
            raise PermissionDenied("Requested school is outside your authorized academic scope.")
        if department and not scope["allowed_departments"].filter(id=department.id).exists():
            raise PermissionDenied("Requested department is outside your authorized academic scope.")
        if course and not scope["allowed_courses"].filter(id=course.id).exists():
            raise PermissionDenied("Requested course is outside your authorized academic scope.")
        if batch and not scope["allowed_batches"].filter(id=batch.id).exists():
            raise PermissionDenied("Requested batch is outside your authorized academic scope.")

        # Bind to authorized scope if entity filters were omitted
        if not school and scope["role"] == "DEAN":
            school = scope["school"]
            if not school:
                raise PermissionDenied("No school assigned to this account.")
        elif not department and scope["role"] == "HOD":
            department = scope["department"]
            if not department:
                raise PermissionDenied("No department assigned to this account.")

    try:
        semester_num = int(semester) if semester else None
    except ValueError:
        semester_num = None

    stats = compute_cohort_deep_dive(
        batch=batch, course=course, semester=semester_num,
        department=department, school=school, user=request.user
    )

    # Privacy filtering for TEACHER: only students in taught batches are named
    is_teacher = request.user.role == "TEACHER"
    taught_batch_ids = set()
    if is_teacher:
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher:
            taught_batch_ids = set(
                TeachingAssignment.objects.filter(teacher=teacher).values_list("batch_id", flat=True)
            )

    clean_topper = None
    if stats["topper"]:
        t_student = stats["topper"].get("student")
        is_named = not is_teacher or (t_student and t_student.batch_id in taught_batch_ids)
        clean_topper = {
            "name": stats["topper"]["name"] if is_named else "Student (Outside Teaching Scope)",
            "roll_no": stats["topper"]["roll_no"] if is_named else "REDACTED",
            "sgpa": stats["topper"]["sgpa"],
            "percentage": stats["topper"]["percentage"],
            "semester": stats["topper"]["semester"],
            "course": stats["topper"]["course"],
        }

    clean_failed = []
    for f in stats["failed_students"][:15]:
        f_student = f.get("student")
        is_named = not is_teacher or (f_student and f_student.batch_id in taught_batch_ids)
        clean_failed.append({
            "name": f["name"] if is_named else "Student (Outside Teaching Scope)",
            "roll_no": f["roll_no"] if is_named else "REDACTED",
            "sgpa": f["sgpa"],
            "percentage": f["percentage"],
            "semester": f["semester"],
            "batch": f["batch"],
        })

    serialized_stats = {
        "total_count": stats["total_count"],
        "min_sgpa": stats["min_sgpa"],
        "max_sgpa": stats["max_sgpa"],
        "avg_sgpa": stats["avg_sgpa"],
        "median_sgpa": stats["median_sgpa"],
        "q1_sgpa": stats["q1_sgpa"],
        "q3_sgpa": stats["q3_sgpa"],
        "topper": clean_topper,
        "failed_students": clean_failed,
        "failed_count": stats["failed_count"],
        "pass_percentage": stats["pass_percentage"],
        "distinction_count": stats.get("distinction_count", 0),
        "most_improved": stats["most_improved"],
        "steepest_drop": stats["steepest_drop"],
        "histogram_bins": stats["histogram_bins"],
        "chart_labels": stats["chart_labels"],
        "chart_data": stats["chart_data"],
    }

    return JsonResponse({"status": "success", "data": serialized_stats})
