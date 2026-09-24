"""
Prediction service adapter for student academic risk forecasting.
Adheres strictly to the ML Feature Contract in edupulse_ml.contract.
Protected demographic attributes and unapproved proxies are strictly banned as inputs.
"""
from academics.models import Subject, SemesterResult
from edupulse_ml.contract import validate_feature_list, validate_row


def get_model():
    """
    Returns the active, registered ML model.
    Returns None until the ModelVersion registry (Task A13) and baseline model (Task A14) are active.
    """
    return None


def predict_current_subjects(student):
    """
    Predicts the expected exam score percentage for all subjects
    in the student's current active semester.
    Returns an empty list when no active model is registered.
    """
    model = get_model()
    if not model:
        return []

    # 1. Fetch current subjects
    current_subjects = Subject.objects.filter(
        course=student.course,
        semester=student.current_semester
    )
    if not current_subjects.exists():
        return []

    # 2. Get behavioral metrics from records without fabricating defaults
    sem_res = SemesterResult.objects.filter(
        student=student,
        semester=student.current_semester
    ).first()
    if not sem_res:
        sem_res = SemesterResult.objects.filter(student=student).order_by("-semester").first()

    attendance = sem_res.attendance_percentage if sem_res and sem_res.attendance_percentage is not None else None
    hours_studied = sem_res.hours_studied_per_week if sem_res and sem_res.hours_studied_per_week is not None else None
    sleep = sem_res.sleep_hours_per_night if sem_res and sem_res.sleep_hours_per_night is not None else None
    previous_score = sem_res.percentage if sem_res and sem_res.percentage is not None else None
    tutoring = sem_res.tutoring_sessions if sem_res and sem_res.tutoring_sessions is not None else None
    physical = sem_res.physical_activity if sem_res and sem_res.physical_activity is not None else None

    # Construct input mapping adhering strictly to the contract
    sample_row = {
        "attendance_percentage": attendance,
        "hours_studied": hours_studied,
        "sleep_hours": sleep,
        "previous_score": previous_score,
        "tutoring_sessions": tutoring,
        "physical_activity": physical,
    }

    problems = validate_row(sample_row)
    if problems:
        # Do not invent default numbers if telemetry is missing
        return []

    predictions = []
    for subject in current_subjects:
        # Once ModelVersion is integrated in A13/A14, inference occurs here
        pass

    return predictions
