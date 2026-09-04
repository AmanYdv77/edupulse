"""
Account views: Home dashboard, results views, ML prediction panels, and Habit Check-in modules.
"""
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta, date

from academics.models import (
    Result, StudentProfile, SemesterResult, Subject, Course, Department,
    StudentHabitPreference, HabitCheckInLog, sync_habits_to_semester_result
)
from academics.forms import HabitCheckInForm, HabitPreferenceForm
from academics.predictor import predict_current_subjects


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


def scoped_results_for(user):
    """
    Return (results_queryset, scope_label) for what THIS user is allowed to see.
    Encodes the academic organizational hierarchy.
    """
    role = user.role

    if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN"):
        return Result.objects.all(), "Entire University"

    if role == "DEAN":
        return (Result.objects.filter(subject__course__department__school=user.school),
                f"School: {user.school}" if user.school else "Your School")

    if role == "HOD":
        return (Result.objects.filter(subject__course__department=user.department),
                f"Department: {user.department}" if user.department else "Your Department")

    if role == "TEACHER":
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            return Result.objects.filter(teacher=teacher), "Students you teach"
        return Result.objects.none(), "Students you teach"

    return Result.objects.none(), "No access"


@login_required
def home(request):
    role = request.user.role
    role_key = "VC" if role in ("REGISTRAR", "CONTROLLER_OF_EXAMS") else role
    dashboard = ROLE_DASHBOARDS.get(role_key, {"title": "Dashboard", "subtitle": "Welcome", "cards": []})
    
    context = {
        "user": request.user,
        "role_label": request.user.get_role_display(),
        "dashboard": dashboard,
        "is_admin": role == "SYSTEM_ADMIN",
    }

    # Student-specific rich dashboard metrics
    if role == "STUDENT":
        student = getattr(request.user, "student_profile", None)
        if student:
            habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
            today = timezone.now().date()
            today_log = student.habit_logs.filter(log_date=today).first()
            recent_logs = student.habit_logs.all()[:5]
            
            # Predictor quick glance
            predictions = predict_current_subjects(student)
            at_risk_count = sum(1 for p in predictions if p["is_at_risk"])
            avg_predicted = (sum(p["predicted_percentage"] for p in predictions) / len(predictions)) if predictions else 0
            
            # Latest semester metrics
            sem_result = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
            if not sem_result:
                sem_result = SemesterResult.objects.filter(student=student).order_by("-semester").first()
                
            form = HabitCheckInForm(initial={"log_type": habit_pref.frequency})
            pref_form = HabitPreferenceForm(instance=habit_pref)
            
            context.update({
                "student": student,
                "habit_pref": habit_pref,
                "today_log": today_log,
                "recent_logs": recent_logs,
                "predictions": predictions,
                "at_risk_count": at_risk_count,
                "avg_predicted": round(avg_predicted, 1),
                "sem_result": sem_result,
                "habit_form": form,
                "pref_form": pref_form,
            })
            
    # Staff-specific rich metrics (Teacher, HOD, Dean, VC)
    elif role in ("TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS"):
        results, scope_label = scoped_results_for(request.user)
        student_ids = results.values_list("student_id", flat=True).distinct()
        student_count = len(student_ids)
        
        # Calculate at-risk count
        sample_students = StudentProfile.objects.filter(id__in=student_ids[:40]).select_related("course", "user")
        at_risk_total = 0
        for s in sample_students:
            preds = predict_current_subjects(s)
            if any(p["is_at_risk"] for p in preds):
                at_risk_total += 1
                
        overall_stats = results.aggregate(avg=Avg("total_secured"), count=Count("id"))
        
        context.update({
            "scope_label": scope_label,
            "student_count": student_count,
            "at_risk_total": at_risk_total,
            "overall_avg": round(overall_stats["avg"] or 0, 1),
            "total_records": overall_stats["count"] or 0,
        })

    return render(request, "home.html", context)


@login_required
def habit_checkin(request):
    """
    Dedicated view for students to log habits, view history, and update frequency preferences.
    """
    student = getattr(request.user, "student_profile", None)
    if not student:
        messages.error(request, "Only students have access to habit check-ins.")
        return redirect("home")

    habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
    today = timezone.now().date()

    if request.method == "POST":
        form = HabitCheckInForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.student = student
            log.log_date = today
            log.save()
            
            # Streak calculation
            if habit_pref.last_checkin_date:
                if habit_pref.last_checkin_date == today - timedelta(days=1):
                    habit_pref.streak_count += 1
                elif habit_pref.last_checkin_date == today:
                    pass  # Already checked in today, keep streak
                else:
                    habit_pref.streak_count = 1
            else:
                habit_pref.streak_count = 1
                
            habit_pref.last_checkin_date = today
            habit_pref.save()
            
            # Sync habits into SemesterResult to update live ML inputs
            sync_habits_to_semester_result(student)
            
            messages.success(request, "🎉 Check-in saved! Your AI performance predictions have been refreshed.")
            return redirect("habit_checkin")
    else:
        # Pre-fill log type based on preference
        form = HabitCheckInForm(initial={"log_type": habit_pref.frequency})

    pref_form = HabitPreferenceForm(instance=habit_pref)
    logs = student.habit_logs.all()[:15]
    today_log = student.habit_logs.filter(log_date=today).first()
    
    # Current behavioral stats
    sem_result = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()

    return render(request, "habit_checkin.html", {
        "student": student,
        "habit_pref": habit_pref,
        "form": form,
        "pref_form": pref_form,
        "logs": logs,
        "today_log": today_log,
        "sem_result": sem_result,
        "today": today,
    })


@login_required
def update_habit_preference(request):
    """
    Endpoint to update Daily vs. Weekly logging frequency preference.
    """
    student = getattr(request.user, "student_profile", None)
    if not student:
        return redirect("home")

    habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
    
    if request.method == "POST":
        form = HabitPreferenceForm(request.POST, instance=habit_pref)
        if form.is_valid():
            form.save()
            messages.success(request, f"Tracking mode updated to {habit_pref.get_frequency_display()}!")
            
    next_url = request.POST.get("next") or "habit_checkin"
    return redirect(next_url)


@login_required
def scoped_results(request):
    """
    A results overview filtered to the logged-in user's scope.
    Used by Teacher / HOD / Dean / VC.
    """
    results, scope_label = scoped_results_for(request.user)

    students = (results
                .values("student__roll_no", "student__user__first_name",
                        "student__user__last_name",
                        "student__course__department__name")
                .annotate(subjects=Count("id"), avg_marks=Avg("total_secured"))
                .order_by("-avg_marks"))

    overall = results.aggregate(avg=Avg("total_secured"), total=Count("id"))

    return render(request, "scoped_results.html", {
        "user": request.user,
        "role_label": request.user.get_role_display(),
        "scope_label": scope_label,
        "students": students,
        "overall": overall,
        "student_count": len(students),
    })


@login_required
def my_results(request):
    """The logged-in STUDENT's own results, grouped by semester."""
    student = getattr(request.user, "student_profile", None)
    if student is None:
        return render(request, "my_results.html", {"no_profile": True})

    results = (student.results
               .select_related("subject", "teacher__user")
               .order_by("semester", "subject__code"))

    semesters = {}
    for r in results:
        s = semesters.setdefault(r.semester, {
            "rows": [], "total_secured": 0, "total_max": 0,
            "total_credit_points": 0.0, "total_credits": 0})
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
        semester_list.append({"semester": sem, "rows": s["rows"], "percentage": pct,
                              "sgpa": sgpa, "status": "PASS" if pct >= 40 else "FAIL"})

    return render(request, "my_results.html", {
        "student": student, "semester_list": semester_list,
        "has_results": bool(semester_list)
    })


@login_required
def my_predictions(request):
    """View to show the logged-in student their current semester predictions."""
    student = getattr(request.user, "student_profile", None)
    if not student:
        return render(request, "my_predictions.html", {"no_profile": True})
        
    predictions = predict_current_subjects(student)
    
    at_risk_count = sum(1 for p in predictions if p["is_at_risk"])
    avg_predicted = sum(p["predicted_percentage"] for p in predictions) / len(predictions) if predictions else 0
    
    behavior = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
    if not behavior:
        behavior = SemesterResult.objects.filter(student=student).order_by("-semester").first()

    return render(request, "my_predictions.html", {
        "student": student,
        "predictions": predictions,
        "at_risk_count": at_risk_count,
        "avg_predicted": round(avg_predicted, 1),
        "behavior": behavior
    })


@login_required
def at_risk_students(request):
    """View for staff to identify students at risk of failing in current subjects."""
    results, scope_label = scoped_results_for(request.user)
    
    student_ids = results.values_list("student_id", flat=True).distinct()
    students = StudentProfile.objects.filter(id__in=student_ids).select_related("user", "course")
    
    at_risk_list = []
    for student in students:
        predictions = predict_current_subjects(student)
        failing_subjects = [p for p in predictions if p["is_at_risk"]]
        if failing_subjects:
            behavior = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
            if not behavior:
                behavior = SemesterResult.objects.filter(student=student).order_by("-semester").first()
                
            at_risk_list.append({
                "student": student,
                "failing_subjects": failing_subjects,
                "behavior": behavior,
                "avg_risk_score": round(sum(p["predicted_percentage"] for p in failing_subjects) / len(failing_subjects), 1)
            })
            
    return render(request, "at_risk_students.html", {
        "scope_label": scope_label,
        "at_risk_list": at_risk_list,
        "total_at_risk": len(at_risk_list)
    })
