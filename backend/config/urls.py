"""
Root URL routing configuration for the EduPulse application.
Dispatches to domain application routing tables.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from api.permissions import StaffOrDevOnly

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("accounts.urls")),
    path("", include("academics.urls")),
    path("", include("predictions.urls")),
    path("", include("analytics.urls")),
    path("api/v1/", include("api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[StaffOrDevOnly]), name="swagger-ui"),
]
