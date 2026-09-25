"""
Root URL routing configuration for the EduPulse application.
Dispatches to domain application routing tables.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("accounts.urls")),
    path("", include("academics.urls")),
    path("", include("predictions.urls")),
    path("", include("analytics.urls")),
]
