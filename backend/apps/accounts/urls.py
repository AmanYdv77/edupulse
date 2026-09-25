"""URL mapping for the accounts app."""

from django.urls import path
from .views import dashboard

urlpatterns = [
    path("", dashboard.index, name="index"),
    path("dashboard/", dashboard.home, name="home"),
]
