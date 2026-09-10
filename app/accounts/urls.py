"""URL map for the 'accounts' app."""
from django.urls import path
from . import views
from . import analytics_views

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.home, name="home"),
    path("analytics/", analytics_views.analytics_hub, name="analytics_hub"),
    path("analytics/api/cohort-query/", analytics_views.api_cohort_query, name="api_cohort_query"),
    path("my-results/", views.my_results, name="my_results"),
    path("results-overview/", views.scoped_results, name="scoped_results"),
    path("my-predictions/", views.my_predictions, name="my_predictions"),
    path("at-risk/", views.at_risk_students, name="at_risk_students"),
    path("teacher/internal-marks/", views.teacher_internal_marks, name="teacher_internal_marks"),
    path("habits/check-in/", views.habit_checkin, name="habit_checkin"),
    path("habits/preference/", views.update_habit_preference, name="update_habit_preference"),
]

