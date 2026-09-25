"""URL routing configuration for the analytics domain."""

from django.urls import path
from . import views

urlpatterns = [
    path("analytics/", views.analytics_hub, name="analytics_hub"),
]

