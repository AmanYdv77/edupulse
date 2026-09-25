"""
Accounts views package.
Re-exports core views and maintains backward-compatible aliases for legacy test imports.
"""

from .dashboard import index, home
from academics.selectors import scoped_results_for
from academics.views import (
    my_results,
    scoped_results,
    teacher_internal_marks,
    habit_checkin,
    update_habit_preference,
)
from predictions.views import my_predictions, at_risk_students

__all__ = [
    "index",
    "home",
    "scoped_results_for",
    "my_results",
    "scoped_results",
    "teacher_internal_marks",
    "habit_checkin",
    "update_habit_preference",
    "my_predictions",
    "at_risk_students",
]
