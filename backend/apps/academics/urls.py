"""URL routing configuration for the academics domain."""

from django.urls import path
from . import views

urlpatterns = [
    path("my-results/", views.my_results, name="my_results"),
    path("results-overview/", views.scoped_results, name="scoped_results"),
    path("teacher/internal-marks/", views.teacher_internal_marks, name="teacher_internal_marks"),
    path("habits/check-in/", views.habit_checkin, name="habit_checkin"),
    path("habits/preference/", views.update_habit_preference, name="update_habit_preference"),
]
