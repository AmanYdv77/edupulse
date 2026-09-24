"""
Tests for Task A16: Strict separation of self-reported habit telemetry from official SemesterResults.
Verifies nullable habit fields on SemesterResult, habit_summary service correctness,
and that check-in submissions do NOT mutate official academic records.
"""
from datetime import timedelta
import pathlib
import pytest
import warnings
from django.utils import timezone
from django.urls import reverse

from academics.models import SemesterResult, HabitCheckInLog, StudentHabitPreference, sync_habits_to_semester_result
from academics.services.habits import habit_summary, HabitSummary
from tests.factories import StudentProfileFactory


@pytest.mark.django_db
def test_semester_result_habit_fields_default_to_none():
    """
    A newly created official SemesterResult must have None for all habit/telemetry fields.
    Zero or fabricated defaults must not be invented.
    """
    student = StudentProfileFactory()
    sem_res = SemesterResult.objects.create(
        student=student,
        semester=1,
        total_max=500,
        total_secured=400,
        sgpa=8.0,
        percentage=80.0,
    )

    assert sem_res.attendance_percentage is None
    assert sem_res.hours_studied_per_week is None
    assert sem_res.sleep_hours_per_night is None
    assert sem_res.motivation_level is None
    assert sem_res.tutoring_sessions is None
    assert sem_res.physical_activity is None
    assert sem_res.extracurricular_activities is None
    assert sem_res.parental_involvement is None
    assert sem_res.peer_influence is None


@pytest.mark.django_db
def test_habit_summary_empty_when_no_logs():
    """
    When a student has no habit check-in logs, habit_summary returns all None values
    and sample_count == 0. Does not mutate or create SemesterResult.
    """
    student = StudentProfileFactory()
    initial_sem_count = SemesterResult.objects.filter(student=student).count()

    summary = habit_summary(student)

    assert isinstance(summary, HabitSummary)
    assert summary.sample_count == 0
    assert summary.hours_studied_per_week is None
    assert summary.sleep_hours_per_night is None
    assert summary.motivation_level is None
    assert summary.tutoring_sessions is None
    assert summary.physical_activity is None

    # Verify no SemesterResult was created
    assert SemesterResult.objects.filter(student=student).count() == initial_sem_count


@pytest.mark.django_db
def test_habit_summary_with_daily_logs():
    """
    Aggregates daily logs into rolling weekly study rate and average sleep hours.
    Does not touch SemesterResult.
    """
    student = StudentProfileFactory()
    today = timezone.now().date()

    # Log 3 daily check-ins: 3.0h study, 7.0h sleep, etc.
    for i in range(3):
        HabitCheckInLog.objects.create(
            student=student,
            log_date=today - timedelta(days=i),
            log_type="DAILY",
            hours_studied=3.0,
            sleep_hours=8.0,
            motivation_level="High",
            tutoring_sessions=1,
            physical_activity=2,
        )

    summary = habit_summary(student)

    assert summary.sample_count == 3
    # 3.0 daily * 7 = 21.0 weekly hours
    assert summary.hours_studied_per_week == 21.0
    assert summary.sleep_hours_per_night == 8.0
    assert summary.motivation_level == "High"
    assert summary.tutoring_sessions == 1
    assert summary.physical_activity == 2

    # Verification: no SemesterResult created
    assert SemesterResult.objects.filter(student=student).count() == 0


@pytest.mark.django_db
def test_habit_summary_respects_window_days():
    """
    Logs outside the window_days parameter are excluded from the summary.
    """
    student = StudentProfileFactory()
    today = timezone.now().date()

    # Old log (40 days ago)
    HabitCheckInLog.objects.create(
        student=student,
        log_date=today - timedelta(days=40),
        log_type="DAILY",
        hours_studied=10.0,
        sleep_hours=4.0,
    )
    # Recent log (2 days ago)
    HabitCheckInLog.objects.create(
        student=student,
        log_date=today - timedelta(days=2),
        log_type="DAILY",
        hours_studied=2.0,
        sleep_hours=7.0,
        motivation_level="Medium",
    )

    summary = habit_summary(student, window_days=28)
    assert summary.sample_count == 1
    assert summary.hours_studied_per_week == 14.0  # 2.0 * 7
    assert summary.sleep_hours_per_night == 7.0


@pytest.mark.django_db
def test_checkin_post_does_not_mutate_semester_result(client):
    """
    Posting a habit check-in updates habit logs and streaks, but leaves
    SemesterResult completely untouched.
    """
    student = StudentProfileFactory()
    client.force_login(student.user)

    # Ensure an official SemesterResult exists with distinct official values
    official_sem = SemesterResult.objects.create(
        student=student,
        semester=student.current_semester,
        total_max=600,
        total_secured=480,
        sgpa=8.5,
        percentage=80.0,
        attendance_percentage=92.0,
        hours_studied_per_week=None,
        sleep_hours_per_night=None,
    )

    url = reverse("habit_checkin")
    post_data = {
        "log_type": "DAILY",
        "hours_studied": 4.5,
        "sleep_hours": 6.5,
        "motivation_level": "High",
        "tutoring_sessions": 2,
        "physical_activity": 3,
        "notes": "Focused study session on algorithms.",
    }

    response = client.post(url, data=post_data, follow=True)
    assert response.status_code == 200

    # Verify HabitCheckInLog was created
    assert HabitCheckInLog.objects.filter(student=student).count() == 1
    log = HabitCheckInLog.objects.filter(student=student).first()
    assert log.hours_studied == 4.5

    # CRITICAL: Verify official_sem was NOT overwritten!
    official_sem.refresh_from_db()
    assert official_sem.attendance_percentage == 92.0  # official attendance unchanged
    assert official_sem.hours_studied_per_week is None  # NOT overwritten by 4.5 * 7
    assert official_sem.sleep_hours_per_night is None  # NOT overwritten by 6.5


@pytest.mark.django_db
def test_deprecated_sync_habits_emits_warning_and_does_not_mutate():
    """
    The deprecated sync_habits_to_semester_result helper emits a DeprecationWarning
    and does NOT modify or create SemesterResult records.
    """
    student = StudentProfileFactory()
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        res = sync_habits_to_semester_result(student)

        # Ensure warning was emitted
        assert len(recorded_warnings) >= 1
        assert issubclass(recorded_warnings[0].category, DeprecationWarning)
        assert "deprecated" in str(recorded_warnings[0].message)

    # Must not have created a SemesterResult
    assert SemesterResult.objects.filter(student=student).count() == 0


def test_no_hardcoded_habit_defaults_in_codebase():
    """
    Scanner invariant: ensure hardcoded default '85.0' or fabricated attendance defaults
    are not present in app/academics or app/accounts or app/predictions.
    """
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    forbidden_tokens = ["attendance_percentage\": 85.0", "attendance_percentage = 85.0"]

    for py_file in app_dir.rglob("*.py"):
        # Skip migrations and test files
        if "migrations" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"Found forbidden token '{token}' in {py_file}"
