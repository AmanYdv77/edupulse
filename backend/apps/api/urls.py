"""
URL configuration for the EduPulse Core REST API (/api/v1/).
"""

from django.urls import path
from .views import (
    CSRFView,
    LoginView,
    LogoutView,
    UserMeView,
    StudentResultsView,
    StudentPredictionsView,
    HabitCheckInListCreateView,
    TeachingAssignmentsView,
    BulkInternalMarksView,
    ModelVersionListView,
)
from analytics.api_views import (
    AnalyticsOverviewAPIView,
    AnalyticsBreakdownAPIView,
    AnalyticsTrendAPIView,
    AnalyticsDistributionAPIView,
    AtRiskRosterAPIView,
    AtRiskExportCSVAPIView,
)

app_name = "api_v1"

urlpatterns = [
    # Auth & Identity
    path("csrf/", CSRFView.as_view(), name="csrf"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", UserMeView.as_view(), name="me"),

    # Academic & Predictions
    path("students/<int:id>/results/", StudentResultsView.as_view(), name="student-results"),
    path("students/<int:id>/predictions/", StudentPredictionsView.as_view(), name="student-predictions"),

    # Habits Check-In
    path("habits/check-ins/", HabitCheckInListCreateView.as_view(), name="habit-checkins"),

    # Faculty & Marks
    path("teaching-assignments/", TeachingAssignmentsView.as_view(), name="teaching-assignments"),
    path("internal-marks/", BulkInternalMarksView.as_view(), name="internal-marks"),

    # Model Registry
    path("models/", ModelVersionListView.as_view(), name="models"),

    # Analytics API Family
    path("analytics/overview/", AnalyticsOverviewAPIView.as_view(), name="analytics-overview"),
    path("analytics/breakdown/", AnalyticsBreakdownAPIView.as_view(), name="analytics-breakdown"),
    path("analytics/trend/", AnalyticsTrendAPIView.as_view(), name="analytics-trend"),
    path("analytics/distribution/", AnalyticsDistributionAPIView.as_view(), name="analytics-distribution"),
    path("analytics/at-risk/", AtRiskRosterAPIView.as_view(), name="analytics-at-risk"),
    path("analytics/export/at-risk.csv", AtRiskExportCSVAPIView.as_view(), name="analytics-export-at-risk"),
]

