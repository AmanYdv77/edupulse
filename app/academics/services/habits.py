from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from django.utils import timezone


@dataclass(frozen=True)
class HabitSummary:
    hours_studied_per_week: Optional[float]
    sleep_hours_per_night: Optional[float]
    motivation_level: Optional[str]
    tutoring_sessions: Optional[int]
    physical_activity: Optional[int]
    sample_count: int


def habit_summary(
    student,
    semester: Optional[int] = None,
    window_days: int = 28,
) -> HabitSummary:
    """
    Computes rolling behavioral habit summary metrics from self-reported HabitCheckInLog records.

    CRITICAL (Task A16):
    - This is a READ-ONLY aggregation service.
    - It NEVER writes to, modifies, or creates SemesterResult rows.
    - Official academic examination results must remain strictly separate from self-reported habit check-ins.
    - When no logs exist, all metric fields return None (no invented fallback constants like 85.0 or 7.0).
    """
    today = timezone.now().date()
    cutoff_date = today - timedelta(days=window_days)

    logs_qs = student.habit_logs.filter(log_date__gte=cutoff_date).order_by("-log_date", "-id")

    sample_count = logs_qs.count()
    if sample_count == 0:
        return HabitSummary(
            hours_studied_per_week=None,
            sleep_hours_per_night=None,
            motivation_level=None,
            tutoring_sessions=None,
            physical_activity=None,
            sample_count=0,
        )

    weekly_logs = list(logs_qs.filter(log_type="WEEKLY"))
    daily_logs = list(logs_qs.filter(log_type="DAILY"))

    if weekly_logs and not daily_logs:
        avg_study = sum(log.hours_studied for log in weekly_logs) / len(weekly_logs)
        avg_sleep = sum(log.sleep_hours for log in weekly_logs) / len(weekly_logs)
        latest = weekly_logs[0]
        motivation = latest.motivation_level
        tutoring = latest.tutoring_sessions
        physical = latest.physical_activity
    elif daily_logs and not weekly_logs:
        avg_daily_study = sum(log.hours_studied for log in daily_logs) / len(daily_logs)
        avg_study = avg_daily_study * 7.0
        avg_sleep = sum(log.sleep_hours for log in daily_logs) / len(daily_logs)
        latest = daily_logs[0]
        motivation = latest.motivation_level
        tutoring = latest.tutoring_sessions
        physical = latest.physical_activity
    else:
        total_weekly_study_units = sum(log.hours_studied * 7.0 for log in daily_logs) + sum(log.hours_studied for log in weekly_logs)
        total_count = len(daily_logs) + len(weekly_logs)
        avg_study = total_weekly_study_units / total_count if total_count else None

        avg_sleep = sum(log.sleep_hours for log in logs_qs) / sample_count if sample_count else None
        latest = logs_qs.first()
        motivation = latest.motivation_level if latest else None
        tutoring = latest.tutoring_sessions if latest else None
        physical = latest.physical_activity if latest else None

    return HabitSummary(
        hours_studied_per_week=round(avg_study, 1) if avg_study is not None else None,
        sleep_hours_per_night=round(avg_sleep, 1) if avg_sleep is not None else None,
        motivation_level=motivation,
        tutoring_sessions=tutoring,
        physical_activity=physical,
        sample_count=sample_count,
    )
