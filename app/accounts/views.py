from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import render

from academics.models import Result, StudentProfile, SemesterResult
from academics.predictor import predict_current_subjects

# ---------------------------------------------------------------------------
# Milestone 5: the HIERARCHY on real data.
#
# The key idea: ONE function builds a "scoped" set of results depending on who
# is logged in. Higher roles see more; lower roles see less. This is the heart
# of "who sees what".
# ---------------------------------------------------------------------------

ROLE_DASHBOARDS = {
    "STUDENT": {
        "title": "My Dashboard", "subtitle": "Track your academic performance",
        "cards": [
            {"icon": "📄", "label": "My Results", "desc": "View your semester-wise marks & grade cards", "link": "my_results"},
            {"icon": "📈", "label": "My Progress", "desc": "See your SGPA trend across semesters"},
            {"icon": "🔮", "label": "Score Prediction", "desc": "Predicted score & at-risk alerts based on behavioral factors", "link": "my_predictions"},
        ],
    },
    "TEACHER": {
        "title": "Teacher Dashboard", "subtitle": "Your classes and students",
        "cards": [
            {"icon": "👨‍🏫", "label": "My Classes & Results", "desc": "Results of students you teach", "link": "scoped_results"},
            {"icon": "📝", "label": "Enter Marks", "desc": "Coming soon: add/update results"},
            {"icon": "⚠️", "label": "At-Risk Students", "desc": "Spot students failing or needing early intervention", "link": "at_risk_students"},
        ],
    },
    "HOD": {
        "title": "Department Dashboard", "subtitle": "Overview of your department",
        "cards": [
            {"icon": "🏢", "label": "Department Results", "desc": "All results in your department", "link": "scoped_results"},
            {"icon": "👩‍🏫", "label": "Teachers", "desc": "Coming soon: teacher performance"},
            {"icon": "🏆", "label": "Toppers", "desc": "Coming soon: department toppers"},
        ],
    },
    "DEAN": {
        "title": "School Dashboard", "subtitle": "Overview of your school",
        "cards": [
            {"icon": "🏫", "label": "School Results", "desc": "All results across your school's departments", "link": "scoped_results"},
            {"icon": "📊", "label": "Department Comparison", "desc": "Coming soon"},
            {"icon": "🏆", "label": "Toppers", "desc": "Coming soon: school toppers"},
        ],
    },
    "VC": {
        "title": "University Dashboard", "subtitle": "University-wide overview",
        "cards": [
            {"icon": "🎓", "label": "University Results", "desc": "All results across the university", "link": "scoped_results"},
            {"icon": "📊", "label": "School Comparison", "desc": "Coming soon"},
            {"icon": "🏆", "label": "University Toppers", "desc": "Coming soon"},
        ],
    },
    "SYSTEM_ADMIN": {
        "title": "Admin Dashboard", "subtitle": "Manage the system & data",
        "cards": [
            {"icon": "🛠️", "label": "Admin Panel", "desc": "Add/edit users, results & records"},
            {"icon": "📥", "label": "Bulk Import", "desc": "Coming soon: upload via CSV"},
            {"icon": "👥", "label": "Manage Users", "desc": "Create logins and assign roles"},
        ],
    },
}


def scoped_results_for(user):
    """
    Return (results_queryset, scope_label) for what THIS user is allowed to see.
    This single function encodes the whole hierarchy.
    """
    role = user.role

    if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN"):
        return Result.objects.all(), "Entire University"

    if role == "DEAN":
        # Everything in the dean's school (all its departments)
        return (Result.objects.filter(subject__course__department__school=user.school),
                f"School: {user.school}" if user.school else "Your School")

    if role == "HOD":
        # Everything in the HOD's department
        return (Result.objects.filter(subject__course__department=user.department),
                f"Department: {user.department}" if user.department else "Your Department")

    if role == "TEACHER":
        # Only results the teacher actually taught
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            return Result.objects.filter(teacher=teacher), "Students you teach"
        return Result.objects.none(), "Students you teach"

    # Students don't use this page (they have my_results); return nothing.
    return Result.objects.none(), "No access"


@login_required
def home(request):
    role = request.user.role
    role_key = "VC" if role in ("REGISTRAR", "CONTROLLER_OF_EXAMS") else role
    dashboard = ROLE_DASHBOARDS.get(role_key, {"title": "Dashboard", "subtitle": "Welcome", "cards": []})
    return render(request, "home.html", {
        "user": request.user,
        "role_label": request.user.get_role_display(),
        "dashboard": dashboard,
        "is_admin": role == "SYSTEM_ADMIN",
    })


@login_required
def scoped_results(request):
    """
    A results overview filtered to the logged-in user's scope.
    Used by Teacher / HOD / Dean / VC. Shows per-student summary + overall stats.
    """
    results, scope_label = scoped_results_for(request.user)

    # Per-student summary (avg %, number of subjects)
    students = (results
                .values("student__roll_no", "student__user__first_name",
                        "student__user__last_name",
                        "student__course__department__name")
                .annotate(subjects=Count("id"), avg_marks=Avg("total_secured"))
                .order_by("-avg_marks"))

    # Overall stats
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
    """The logged-in STUDENT's own results, grouped by semester (from M4)."""
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
        "has_results": bool(semester_list)})


@login_required
def my_predictions(request):
    """View to show the logged-in student their current semester predictions."""
    student = getattr(request.user, "student_profile", None)
    if not student:
        return render(request, "my_predictions.html", {"no_profile": True})
        
    predictions = predict_current_subjects(student)
    
    # Calculate summary stats
    at_risk_count = sum(1 for p in predictions if p['is_at_risk'])
    avg_predicted = sum(p['predicted_percentage'] for p in predictions) / len(predictions) if predictions else 0
    
    # Get student's behavioral metrics for display
    behavior = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
    if not behavior:
        behavior = SemesterResult.objects.filter(student=student).order_by('-semester').first()

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
    
    # Get distinct students in this staff member's scope
    student_ids = results.values_list('student_id', flat=True).distinct()
    students = StudentProfile.objects.filter(id__in=student_ids).select_related('user', 'course')
    
    at_risk_list = []
    for student in students:
        predictions = predict_current_subjects(student)
        failing_subjects = [p for p in predictions if p['is_at_risk']]
        if failing_subjects:
            # Fetch latest behavior for risk context
            behavior = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
            if not behavior:
                behavior = SemesterResult.objects.filter(student=student).order_by('-semester').first()
                
            at_risk_list.append({
                "student": student,
                "failing_subjects": failing_subjects,
                "behavior": behavior
            })
            
    return render(request, "at_risk_students.html", {
        "scope_label": scope_label,
        "at_risk_list": at_risk_list,
        "total_at_risk": len(at_risk_list)
    })
