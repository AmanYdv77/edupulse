"""
Views for student behavioral telemetry check-in and tracking frequency preference.
"""

from datetime import timedelta
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone

from accounts.permissions import role_required
from academics.models import SemesterResult, StudentHabitPreference
from academics.services.habits import habit_summary
from academics.forms import HabitCheckInForm, HabitPreferenceForm


@role_required("STUDENT")
def habit_checkin(request):
    """Dedicated view for students to log habits, view history, and update frequency preferences."""
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
                    pass  # Already checked in today, maintain streak
                else:
                    habit_pref.streak_count = 1
            else:
                habit_pref.streak_count = 1

            habit_pref.last_checkin_date = today
            habit_pref.save()

            messages.success(request, "🎉 Check-in saved! Your telemetry log has been recorded.")
            return redirect("habit_checkin")
    else:
        form = HabitCheckInForm(initial={"log_type": habit_pref.frequency})

    pref_form = HabitPreferenceForm(instance=habit_pref)
    logs = student.habit_logs.all()[:15]
    today_log = student.habit_logs.filter(log_date=today).first()
    sem_result = SemesterResult.objects.filter(student=student, semester=student.current_semester).first()
    summary = habit_summary(student)

    return render(request, "habit_checkin.html", {
        "student": student,
        "habit_pref": habit_pref,
        "form": form,
        "pref_form": pref_form,
        "logs": logs,
        "today_log": today_log,
        "sem_result": sem_result,
        "habit_summary": summary,
        "today": today,
    })


@role_required("STUDENT")
def update_habit_preference(request):
    """Endpoint to update Daily vs. Weekly logging frequency preference."""
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
