"""
Role-Specific Analytics View Controllers and JSON Query API.
Dispatches to tailored Monolith Dark analytics templates for Student, Teacher, HOD, Dean, and Executive.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

from academics.models import (
    StudentProfile, TeacherProfile, Department, School, Course, Batch
)
from academics.analytics_engine import (
    compute_cohort_deep_dive, get_student_analytics, get_teacher_analytics,
    get_hod_analytics, get_dean_analytics, get_executive_analytics
)


@login_required
def analytics_hub(request):
    """
    Central dispatcher routing each user to their specific analytical cockpit.
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
        dept = user.department or (user.teacher_profile.department if hasattr(user, "teacher_profile") else None) or Department.objects.first()
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
        school = user.school or School.objects.first()
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


@login_required
@require_GET
def api_cohort_query(request):
    """
    JSON API for dynamic statistical drill-downs:
    Answers: Topper, Failures count & list, 5-number summary (Min, Max, Avg, Median, Q1, Q3),
    Pass %, Most Improved, Steepest Drop, and distribution bins.
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
    
    try:
        semester_num = int(semester) if semester else None
    except ValueError:
        semester_num = None

    stats = compute_cohort_deep_dive(
        batch=batch, course=course, semester=semester_num,
        department=department, school=school
    )

    # Clean student objects for JSON serialization
    clean_topper = None
    if stats["topper"]:
        clean_topper = {
            "name": stats["topper"]["name"],
            "roll_no": stats["topper"]["roll_no"],
            "sgpa": stats["topper"]["sgpa"],
            "percentage": stats["topper"]["percentage"],
            "semester": stats["topper"]["semester"],
            "course": stats["topper"]["course"],
        }

    clean_failed = []
    for f in stats["failed_students"][:15]:
        clean_failed.append({
            "name": f["name"],
            "roll_no": f["roll_no"],
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
