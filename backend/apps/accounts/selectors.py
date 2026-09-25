"""
Data selectors and query builders for the accounts domain.
Extracts dashboard telemetry and KPI computation out of view handlers.
"""

from datetime import timedelta
from django.db.models import Avg, Count
from django.utils import timezone

from academics.models import (
    Result,
    StudentProfile,
    SemesterResult,
    Course,
    Department,
    School,
    University,
    TeacherProfile,
    TeachingAssignment,
    InternalAssessment,
    StudentHabitPreference,
)
from academics.forms import HabitCheckInForm, HabitPreferenceForm
from predictions.services import predict_for_students, predict_current_subjects


ROLE_DASHBOARDS = {
    "STUDENT": {
        "title": "Student Portal",
        "subtitle": "Your academic journey, live predictions, and habit tracker",
        "cards": [
            {"icon": "📊", "label": "My Results", "desc": "Official semester grade cards & transcripts", "link": "my_results"},
            {"icon": "🔮", "label": "AI Performance Predictor", "desc": "Smart grade forecast & study advisor", "link": "my_predictions"},
            {"icon": "⚡", "label": "Habit & Study Check-in", "desc": "Log study hours & sleep to power your AI advisor", "link": "habit_checkin"},
        ],
    },
    "TEACHER": {
        "title": "Faculty Dashboard",
        "subtitle": "Manage your assigned classes, marks, and student interventions",
        "cards": [
            {"icon": "👥", "label": "Assigned Students", "desc": "View academic progress for your batches", "link": "scoped_results"},
            {"icon": "⚠️", "label": "At-Risk Early Warning", "desc": "Identify and assist students predicted to struggle", "link": "at_risk_students"},
            {"icon": "📝", "label": "Attendance & Marks", "desc": "Daily class attendance & grade management"},
        ],
    },
    "HOD": {
        "title": "Department Dashboard",
        "subtitle": "Department-level academic oversight, risk tracking, and analytics",
        "cards": [
            {"icon": "🏛️", "label": "Department Results", "desc": "Comprehensive results across all department batches", "link": "scoped_results"},
            {"icon": "⚠️", "label": "At-Risk Overview", "desc": "Department-wide student intervention alerts", "link": "at_risk_students"},
            {"icon": "📈", "label": "Course Analytics", "desc": "Batch comparisons and pass-rate trends"},
        ],
    },
    "DEAN": {
        "title": "School Dashboard",
        "subtitle": "Executive academic overview across all school departments",
        "cards": [
            {"icon": "🏫", "label": "School Results", "desc": "All results across your school's departments", "link": "scoped_results"},
            {"icon": "⚠️", "label": "School Risk Heatmap", "desc": "At-risk distribution by department", "link": "at_risk_students"},
            {"icon": "🏆", "label": "Merit & Toppers", "desc": "School-level rank holders and excellence"},
        ],
    },
    "VC": {
        "title": "Institutional Dashboard",
        "subtitle": "University-wide executive analytics and performance metrics",
        "cards": [
            {"icon": "🎓", "label": "University Results", "desc": "Institution-wide results across all schools", "link": "scoped_results"},
            {"icon": "📊", "label": "School Benchmarks", "desc": "Comparative school analytics and trends"},
            {"icon": "⚠️", "label": "Institutional Risk Board", "desc": "Global student support alert board", "link": "at_risk_students"},
        ],
    },
    "SYSTEM_ADMIN": {
        "title": "Administration Hub",
        "subtitle": "Manage system configurations, user roles, databases, and ML models",
        "cards": [
            {"icon": "⚙️", "label": "Django Admin Console", "desc": "Manage database records, models, and permissions", "link": "/admin/"},
            {"icon": "📥", "label": "Data Pipelines & ETL", "desc": "Batch student imports and schema sync tools"},
            {"icon": "🤖", "label": "ML Model Registry", "desc": "Model weights, retraining triggers, and accuracy metrics"},
        ],
    },
}


def get_student_dashboard_context(user) -> dict:
    """Computes student dashboard telemetry, habits form, and trajectory chart."""
    student = getattr(user, "student_profile", None)
    if not student:
        return {}

    habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
    today = timezone.now().date()
    today_log = student.habit_logs.filter(log_date=today).first()
    recent_logs = student.habit_logs.all()[:5]

    predictions = predict_current_subjects(student)
    at_risk_count = sum(1 for p in predictions if p["is_at_risk"])
    avg_predicted = (sum(p["predicted_percentage"] for p in predictions) / len(predictions)) if predictions else 0

    published_sems = SemesterResult.objects.filter(student=student, is_published=True).order_by("semester")
    chart_labels = [f"Sem {s.semester}" for s in published_sems]
    chart_sgpa = [round(s.sgpa, 2) for s in published_sems]
    if not chart_labels:
        chart_labels = [f"Sem {student.current_semester} (Est)"]
        chart_sgpa = [round(avg_predicted / 10, 2)] if avg_predicted else [7.5]

    latest_sem = published_sems.last()
    kpi_standing = f"{latest_sem.sgpa:.2f} SGPA" if latest_sem else (f"{round(avg_predicted / 10, 2):.2f} Est" if avg_predicted else "Pending")
    kpi_streak = f"{habit_pref.streak_count} Days"
    kpi_status = "Optimal Trajectory" if at_risk_count == 0 else f"{at_risk_count} Risk Flag{'s' if at_risk_count > 1 else ''}"
    kpi_status_tag = "tag-low-risk" if at_risk_count == 0 else "tag-high-risk"

    recent_assessments = student.internal_assessments.filter(is_submitted=True).select_related("subject")[:6]
    sem_result = SemesterResult.objects.filter(student=student, semester=student.current_semester).first() or latest_sem

    form = HabitCheckInForm(initial={"log_type": habit_pref.frequency})
    pref_form = HabitPreferenceForm(instance=habit_pref)

    return {
        "student": student,
        "habit_pref": habit_pref,
        "today_log": today_log,
        "recent_logs": recent_logs,
        "predictions": predictions,
        "at_risk_count": at_risk_count,
        "avg_predicted": round(avg_predicted, 1),
        "sem_result": sem_result,
        "kpi_standing": kpi_standing,
        "kpi_streak": kpi_streak,
        "kpi_status": kpi_status,
        "kpi_status_tag": kpi_status_tag,
        "chart_labels": chart_labels,
        "chart_sgpa": chart_sgpa,
        "recent_assessments": recent_assessments,
        "habit_form": form,
        "pref_form": pref_form,
    }


def get_teacher_dashboard_context(user) -> dict:
    """Computes faculty assigned batch KPIs, risk radar, and subject average distributions."""
    teacher = getattr(user, "teacher_profile", None)
    assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related("subject", "batch", "batch__course") if teacher else TeachingAssignment.objects.none()
    batch_count = assignments.values("batch").distinct().count()

    teacher_results = Result.objects.filter(teacher=teacher) if teacher else Result.objects.none()
    class_avg_stat = teacher_results.aggregate(avg=Avg("total_secured"))
    class_avg = round(class_avg_stat["avg"] or 72.4, 1)

    assigned_student_ids = teacher_results.values_list("student_id", flat=True).distinct()
    teacher_students = list(StudentProfile.objects.filter(id__in=assigned_student_ids).select_related("user", "course")[:25])
    all_preds = predict_for_students(teacher_students)
    preds_by_student = {}
    for p in all_preds:
        preds_by_student.setdefault(p.student_id, []).append(p)

    at_risk_teacher_list = []
    for s in teacher_students:
        failing = [p for p in preds_by_student.get(s.id, []) if p.is_at_risk]
        if failing:
            valid_scores = [p.predicted_percentage for p in failing if p.predicted_percentage is not None]
            avg_val = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0
            at_risk_teacher_list.append({
                "student": s,
                "failing_subjects": failing,
                "count": len(failing),
                "avg_score": avg_val,
            })
    kpi_at_risk = len(at_risk_teacher_list)

    chart_labels = []
    chart_values = []
    for a in assignments:
        avg_subj = teacher_results.filter(subject=a.subject).aggregate(avg=Avg("total_secured"))["avg"] or class_avg
        chart_labels.append(a.subject.code)
        chart_values.append(round(avg_subj, 1))
    if not chart_labels:
        chart_labels = ["CS101", "CS102", "CS103"]
        chart_values = [74.5, 68.2, 79.0]

    recent_assessments = InternalAssessment.objects.filter(teacher=teacher).select_related("subject", "student")[:6] if teacher else []

    return {
        "teacher": teacher,
        "assignments": assignments,
        "kpi_active_batches": f"{batch_count} Active",
        "kpi_class_avg": f"{class_avg}%",
        "kpi_at_risk": f"{kpi_at_risk} Students",
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "at_risk_list": at_risk_teacher_list[:5],
        "recent_assessments": recent_assessments,
    }


def get_hod_dashboard_context(user) -> dict:
    """Computes department-level pass rate, mark submission rate, and course comparisons."""
    dept = user.department or (user.teacher_profile.department if hasattr(user, "teacher_profile") else None) or Department.objects.first()
    dept_courses = dept.courses.all() if dept else Course.objects.all()
    dept_students = StudentProfile.objects.filter(course__in=dept_courses)
    dept_results = Result.objects.filter(subject__course__in=dept_courses)

    student_count = dept_students.count()
    pass_count = dept_results.filter(total_secured__gte=40).values("student").distinct().count()
    pass_projection = round((pass_count / student_count * 100), 1) if student_count else 88.6

    assignments_in_dept = TeachingAssignment.objects.filter(subject__course__in=dept_courses).select_related("teacher__user", "subject", "batch")
    total_slots = assignments_in_dept.count()
    submitted_slots = assignments_in_dept.filter(subject__internal_assessments__is_submitted=True).distinct().count()
    sub_rate = int((submitted_slots / total_slots) * 100) if total_slots else 100

    chart_labels = []
    chart_values = []
    for c in dept_courses:
        c_avg = dept_results.filter(subject__course=c).aggregate(avg=Avg("total_secured"))["avg"] or 71.0
        chart_labels.append(c.code)
        chart_values.append(round(c_avg, 1))
    if not chart_labels:
        chart_labels = ["BTECH-CSE", "BTECH-IT", "MCA"]
        chart_values = [76.4, 71.8, 74.2]

    return {
        "dept": dept,
        "kpi_dept_pass": f"{pass_projection}%",
        "kpi_dept_students": f"{student_count} Active",
        "kpi_submission_status": f"{sub_rate}% Finalized",
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "faculty_status": assignments_in_dept[:6],
    }


def get_dean_dashboard_context(user) -> dict:
    """Computes school-level benchmarks, enrollment, and department comparisons."""
    school = user.school or School.objects.first()
    school_depts = school.departments.all() if school else Department.objects.all()
    school_students = StudentProfile.objects.filter(course__department__in=school_depts)
    school_results = Result.objects.filter(subject__course__department__in=school_depts)

    school_avg = school_results.aggregate(avg=Avg("total_secured"))["avg"] or 72.8
    school_index = round(school_avg / 10, 2)
    school_enrollment = school_students.count()

    chart_labels = []
    chart_values = []
    dept_summaries = []
    for d in school_depts:
        d_avg = school_results.filter(subject__course__department=d).aggregate(avg=Avg("total_secured"))["avg"] or 70.0
        d_students = school_students.filter(course__department=d).count()
        chart_labels.append(d.name[:16])
        chart_values.append(round(d_avg, 1))
        dept_summaries.append({
            "dept": d,
            "student_count": d_students,
            "avg_score": round(d_avg, 1),
            "status": "On Track" if d_avg >= 60 else "Review Needed",
        })

    return {
        "school": school,
        "kpi_school_index": f"{school_index} / 10",
        "kpi_school_enrollment": f"{school_enrollment} Cohort",
        "kpi_depts_on_target": f"{len(school_depts)} of {len(school_depts)} Normal",
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "dept_summaries": dept_summaries,
    }


def get_executive_dashboard_context(user) -> dict:
    """Computes institutional university-wide aggregate metrics for VC / Registrar."""
    univ = University.objects.first()
    all_schools = School.objects.all()
    all_students_count = StudentProfile.objects.count()
    all_results = Result.objects.all()
    overall_avg = all_results.aggregate(avg=Avg("total_secured"))["avg"] or 73.5
    univ_projection = round(overall_avg, 1)

    chart_labels = []
    chart_values = []
    school_summaries = []
    critical_flags = 0
    for sch in all_schools:
        sch_avg = all_results.filter(subject__course__department__school=sch).aggregate(avg=Avg("total_secured"))["avg"] or overall_avg
        sch_students = StudentProfile.objects.filter(course__department__school=sch).count()
        chart_labels.append(sch.code or sch.name[:14])
        chart_values.append(round(sch_avg, 1))
        is_flagged = sch_avg < 60
        if is_flagged:
            critical_flags += 1
        school_summaries.append({
            "school": sch,
            "student_count": sch_students,
            "avg_score": round(sch_avg, 1),
            "status": "Critical Flag" if is_flagged else "Optimal",
        })

    return {
        "univ": univ,
        "kpi_univ_projection": f"{univ_projection}%",
        "kpi_univ_cohort": f"{all_students_count} Students",
        "kpi_critical_alerts": f"{critical_flags} Alerts",
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "school_summaries": school_summaries,
    }


def get_dashboard_context_for_role(user) -> dict:
    """Orchestrates role-scoped dashboard context loading without monolithic view logic."""
    role = user.role
    role_key = "VC" if role in ("REGISTRAR", "CONTROLLER_OF_EXAMS") else role
    dashboard = ROLE_DASHBOARDS.get(role_key, {"title": "Dashboard", "subtitle": "Welcome", "cards": []})

    context = {
        "user": user,
        "role": role,
        "role_label": user.get_role_display(),
        "dashboard": dashboard,
        "is_admin": role == "SYSTEM_ADMIN",
    }

    if role == "STUDENT":
        context.update(get_student_dashboard_context(user))
    elif role == "TEACHER":
        context.update(get_teacher_dashboard_context(user))
    elif role == "HOD":
        context.update(get_hod_dashboard_context(user))
    elif role == "DEAN":
        context.update(get_dean_dashboard_context(user))
    elif role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS"):
        context.update(get_executive_dashboard_context(user))
    elif role == "SYSTEM_ADMIN" or user.is_superuser:
        pending_publish = SemesterResult.objects.filter(is_published=False).count()
        context.update({
            "kpi_system_status": "Operational",
            "kpi_total_records": Result.objects.count(),
            "kpi_pending_publish": f"{pending_publish} Drafts",
        })

    return context
