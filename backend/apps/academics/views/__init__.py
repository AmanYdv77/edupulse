"""Academics feature view package."""

from .results import my_results, scoped_results
from .internal_marks import teacher_internal_marks
from .habits import habit_checkin, update_habit_preference

__all__ = [
    "my_results",
    "scoped_results",
    "teacher_internal_marks",
    "habit_checkin",
    "update_habit_preference",
]
