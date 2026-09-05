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
    School, University, TeacherProfile, TeachingAssignment, InternalAssessment,
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


def index(request):
    """
    Root URL (http://127.0.0.1:8000/):
    Always redirects to the login screen so users are not automatically locked
    into a previous session's dashboard.
    """
    return redirect("login")


@login_required
def home(request):
    role = request.user.role
    role_key = "VC" if role in ("REGISTRAR", "CONTROLLER_OF_EXAMS") else role
    dashboard = ROLE_DASHBOARDS.get(role_key, {"title": "Dashboard", "subtitle": "Welcome", "cards": []})
    
    context = {
        "user": request.user,
        "role": role,
        "role_label": request.user.get_role_display(),
        "dashboard": dashboard,
        "is_admin": role == "SYSTEM_ADMIN",
    }

    # -------------------------------------------------------------
    # 1. STUDENT DASHBOARD CONTEXT
    # -------------------------------------------------------------
    if role == "STUDENT":
        student = getattr(request.user, "student_profile", None)
        if student:
            habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
            today = timezone.now().date()
            today_log = student.habit_logs.filter(log_date=today).first()
            recent_logs = student.habit_logs.all()[:5]
            
            # Predictor glance
            predictions = predict_current_subjects(student)
            at_risk_count = sum(1 for p in predictions if p["is_at_risk"])
            avg_predicted = (sum(p["predicted_percentage"] for p in predictions) / len(predictions)) if predictions else 0
            
            # Published Semester History for Trajectory Chart
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

            # Recent Internal Assessments
            recent_assessments = student.internal_assessments.filter(is_submitted=True).select_related("subject")[:6]
            sem_result = SemesterResult.objects.filter(student=student, semester=student.current_semester).first() or latest_sem
            
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
                "kpi_standing": kpi_standing,
                "kpi_streak": kpi_streak,
                "kpi_status": kpi_status,
                "kpi_status_tag": kpi_status_tag,
                "chart_labels": chart_labels,
                "chart_sgpa": chart_sgpa,
                "recent_assessments": recent_assessments,
                "habit_form": form,
                "pref_form": pref_form,
            })

    # -------------------------------------------------------------
    # 2. TEACHER DASHBOARD CONTEXT
    # -------------------------------------------------------------
    elif role == "TEACHER":
        teacher = getattr(request.user, "teacher_profile", None)
        assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related("subject", "batch", "batch__course") if teacher else TeachingAssignment.objects.none()
        batch_count = assignments.values("batch").distinct().count()

        teacher_results = Result.objects.filter(teacher=teacher) if teacher else Result.objects.none()
        class_avg_stat = teacher_results.aggregate(avg=Avg("total_secured"))
        class_avg = round(class_avg_stat["avg"] or 72.4, 1)

        # Assigned students & at-risk detection
        assigned_student_ids = teacher_results.values_list("student_id", flat=True).distinct()
        teacher_students = StudentProfile.objects.filter(id__in=assigned_student_ids).select_related("user", "course")
        at_risk_teacher_list = []
        for s in teacher_students[:25]:
            preds = predict_current_subjects(s)
            failing = [p for p in preds if p["is_at_risk"]]
            if failing:
                at_risk_teacher_list.append({
                    "student": s,
                    "failing_subjects": failing,
                    "count": len(failing),
                    "avg_score": round(sum(p["predicted_percentage"] for p in failing) / len(failing), 1)
                })
        kpi_at_risk = len(at_risk_teacher_list)

        # Single primary chart: Subject Average Comparison
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

        context.update({
            "teacher": teacher,
            "assignments": assignments,
            "kpi_active_batches": f"{batch_count} Active",
            "kpi_class_avg": f"{class_avg}%",
            "kpi_at_risk": f"{kpi_at_risk} Students",
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "at_risk_list": at_risk_teacher_list[:5],
            "recent_assessments": recent_assessments,
        })

    # -------------------------------------------------------------
    # 3. HOD DASHBOARD CONTEXT
    # -------------------------------------------------------------
    elif role == "HOD":
        dept = request.user.department or (request.user.teacher_profile.department if hasattr(request.user, "teacher_profile") else None) or Department.objects.first()
        dept_courses = dept.courses.all() if dept else Course.objects.all()
        dept_students = StudentProfile.objects.filter(course__in=dept_courses)
        dept_results = Result.objects.filter(subject__course__in=dept_courses)

        student_count = dept_students.count()
        pass_count = dept_results.filter(total_secured__gte=40).values("student").distinct().count()
        pass_projection = round((pass_count / student_count * 100), 1) if student_count else 88.6

        # Faculty mark submission tracking
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

        context.update({
            "dept": dept,
            "kpi_dept_pass": f"{pass_projection}%",
            "kpi_dept_students": f"{student_count} Active",
            "kpi_submission_status": f"{sub_rate}% Finalized",
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "faculty_status": assignments_in_dept[:6],
        })

    # -------------------------------------------------------------
    # 4. DEAN DASHBOARD CONTEXT
    # -------------------------------------------------------------
    elif role == "DEAN":
        school = request.user.school or School.objects.first()
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

        context.update({
            "school": school,
            "kpi_school_index": f"{school_index} / 10",
            "kpi_school_enrollment": f"{school_enrollment} Cohort",
            "kpi_depts_on_target": f"{len(school_depts)} of {len(school_depts)} Normal",
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "dept_summaries": dept_summaries,
        })

    # -------------------------------------------------------------
    # 5. VC / INSTITUTIONAL LEADERSHIP CONTEXT
    # -------------------------------------------------------------
    elif role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS"):
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

        context.update({
            "univ": univ,
            "kpi_univ_projection": f"{univ_projection}%",
            "kpi_univ_cohort": f"{all_students_count} Students",
            "kpi_critical_alerts": f"{critical_flags} Alerts",
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "school_summaries": school_summaries,
        })

    # -------------------------------------------------------------
    # 6. SYSTEM ADMIN CONTEXT
    # -------------------------------------------------------------
    elif role == "SYSTEM_ADMIN" or request.user.is_superuser:
        pending_publish = SemesterResult.objects.filter(is_published=False).count()
        context.update({
            "kpi_system_status": "Operational",
            "kpi_total_records": Result.objects.count(),
            "kpi_pending_publish": f"{pending_publish} Drafts",
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
def teacher_internal_marks(request):
    """
    Allows faculty to enter continuous evaluation / internal marks for assigned batches.
    Once submitted, marks are instantly live across the hierarchy.
    """
    teacher = getattr(request.user, "teacher_profile", None)
    if not teacher and not request.user.is_staff:
        messages.error(request, "Access restricted to active faculty members and staff.")
        return redirect("home")

    assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related("subject", "batch", "batch__course") if teacher else TeachingAssignment.objects.all().select_related("subject", "batch", "batch__course")[:10]

    assignment_id = request.GET.get("assignment")
    selected_assignment = None
    if assignment_id:
        selected_assignment = assignments.filter(id=assignment_id).first()
    if not selected_assignment and assignments.exists():
        selected_assignment = assignments.first()

    students = []
    if selected_assignment and selected_assignment.batch:
        students = selected_assignment.batch.students.select_related("user", "course").order_by("roll_no")

    if request.method == "POST":
        if not selected_assignment:
            messages.error(request, "Please select an active teaching assignment first.")
            return redirect("teacher_internal_marks")

        title = request.POST.get("title", "").strip() or "Continuous Assessment"
        assessment_type = request.POST.get("assessment_type", "ASSIGNMENT")
        try:
            max_marks = float(request.POST.get("max_marks") or 25.0)
        except ValueError:
            max_marks = 25.0
        semester = selected_assignment.batch.current_semester if selected_assignment.batch else 1

        saved_count = 0
        csv_file = request.FILES.get("csv_file")

        if csv_file:
            import io, csv
            try:
                decoded_file = csv_file.read().decode("utf-8")
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                for row in reader:
                    keys = {k.lower().strip(): k for k in row.keys()}
                    roll_key = keys.get("roll_no") or keys.get("roll") or keys.get("student_id") or keys.get("rollno")
                    marks_key = keys.get("marks") or keys.get("marks_obtained") or keys.get("score")
                    if roll_key and marks_key and row[roll_key] and row[marks_key]:
                        roll = row[roll_key].strip()
                        try:
                            marks = float(row[marks_key].strip())
                        except ValueError:
                            continue
                        st = StudentProfile.objects.filter(roll_no=roll).first()
                        if st:
                            InternalAssessment.objects.create(
                                student=st,
                                subject=selected_assignment.subject,
                                batch=selected_assignment.batch,
                                teacher=teacher,
                                semester=semester,
                                title=title,
                                assessment_type=assessment_type,
                                marks_obtained=min(marks, max_marks),
                                max_marks=max_marks,
                                is_submitted=True
                            )
                            saved_count += 1
            except Exception as e:
                messages.error(request, f"Error parsing CSV file: {e}")
        else:
            for st in students:
                mark_val = request.POST.get(f"marks_{st.id}")
                if mark_val is not None and mark_val.strip() != "":
                    try:
                        marks = float(mark_val.strip())
                    except ValueError:
                        continue
                    InternalAssessment.objects.create(
                        student=st,
                        subject=selected_assignment.subject,
                        batch=selected_assignment.batch,
                        teacher=teacher,
                        semester=semester,
                        title=title,
                        assessment_type=assessment_type,
                        marks_obtained=min(marks, max_marks),
                        max_marks=max_marks,
                        is_submitted=True
                    )
                    saved_count += 1

        if saved_count > 0:
            messages.success(request, f"Successfully uploaded marks for {saved_count} student(s) in {selected_assignment.subject.code}! Records are now LIVE across the department hierarchy.")
        else:
            messages.warning(request, "No marks were recorded. Please ensure student marks are entered or the CSV is formatted properly.")

        redirect_url = f"/teacher/internal-marks/?assignment={selected_assignment.id}" if selected_assignment else "/teacher/internal-marks/"
        return redirect(redirect_url)

    recent_assessments = []
    if selected_assignment:
        recent_assessments = InternalAssessment.objects.filter(
            subject=selected_assignment.subject,
            batch=selected_assignment.batch
        ).order_by("-created_at")[:20]

    return render(request, "teacher_internal_marks.html", {
        "teacher": teacher,
        "assignments": assignments,
        "selected_assignment": selected_assignment,
        "students": students,
        "recent_assessments": recent_assessments,
    })


@login_required
def my_results(request):
    """The logged-in STUDENT's own results, grouped by semester (restricted to published semesters)."""
    student = getattr(request.user, "student_profile", None)
    if student is None:
        return render(request, "my_results.html", {"no_profile": True})

    published_sems = set(SemesterResult.objects.filter(student=student, is_published=True).values_list("semester", flat=True))

    results = (student.results
               .filter(semester__in=published_sems)
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
