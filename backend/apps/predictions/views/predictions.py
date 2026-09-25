"""
Views for student machine learning predictions and staff at-risk radar.
"""

from types import SimpleNamespace
from django.shortcuts import render

from accounts.permissions import role_required
from academics.models import SemesterResult
from academics.services.habits import habit_summary
from ..services import predict_current_subjects
from ..selectors import scoped_snapshots_for


@role_required("STUDENT")
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

    habits = habit_summary(student)

    return render(request, "my_predictions.html", {
        "student": student,
        "predictions": predictions,
        "at_risk_count": at_risk_count,
        "avg_predicted": round(avg_predicted, 1),
        "behavior": behavior,
        "habits": habits,
    })


@role_required("TEACHER", "HOD", "DEAN", "VC", "REGISTRAR", "CONTROLLER_OF_EXAMS", "SYSTEM_ADMIN")
def at_risk_students(request):
    """
    View for staff to identify students at risk of failing in current subjects.
    Reads pre-computed PredictionSnapshot records within the user's organizational scope.
    Operates in O(1) constant queries bounded by performance budget.
    """
    snapshots_qs, scope_label = scoped_snapshots_for(request.user)

    snapshots = list(
        snapshots_qs.select_related("student__user", "subject")
        .order_by("-taken_at", "-id")[:500]
    )

    seen_pairs = set()
    students_map = {}

    for snap in snapshots:
        key = (snap.student_id, snap.subject_id)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)

        if snap.risk_band in ("high", "insufficient_data"):
            if snap.student_id not in students_map:
                feats = snap.features or {}
                behavior = SimpleNamespace(
                    hours_studied_per_week=feats.get("hours_studied"),
                    attendance_percentage=feats.get("attendance_percentage"),
                    sleep_hours_per_night=feats.get("sleep_hours"),
                )
                habits = SimpleNamespace(
                    hours_studied_per_week=feats.get("hours_studied"),
                    sleep_hours_per_night=feats.get("sleep_hours"),
                )
                students_map[snap.student_id] = {
                    "student": snap.student,
                    "failing_subjects": [],
                    "behavior": behavior,
                    "habits": habits,
                }
            students_map[snap.student_id]["failing_subjects"].append({
                "subject_code": snap.subject.code,
                "subject_title": snap.subject.title,
                "predicted_percentage": snap.predicted_percentage,
                "is_at_risk": True,
                "risk_band": snap.risk_band,
                "reasons": snap.reasons,
            })

    at_risk_list = []
    for item in students_map.values():
        failing = item["failing_subjects"]
        valid_scores = [p["predicted_percentage"] for p in failing if p["predicted_percentage"] is not None]
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0
        item["avg_risk_score"] = avg_score
        at_risk_list.append(item)

    return render(request, "at_risk_students.html", {
        "scope_label": scope_label,
        "at_risk_list": at_risk_list,
        "total_at_risk": len(at_risk_list),
    })
