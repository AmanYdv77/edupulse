"""
Root URL routing configuration for the EduPulse application.
Serves the versioned REST API (/api/v1/), OpenAPI documentation, Django Admin,
and the React Single-Page Application (SPA) at /app/.
"""

from api.permissions import StaffOrDevOnly
from core.spa import SPAIndexView
from core.views import HealthCheckView, ReadinessCheckView
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("ready/", ReadinessCheckView.as_view(), name="readiness"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[StaffOrDevOnly]),
        name="swagger-ui",
    ),
    path("", RedirectView.as_view(url="/app/", permanent=False), name="root-redirect"),
    path("app/", SPAIndexView.as_view(), name="spa-root"),
    path("app/<path:path>", SPAIndexView.as_view(), name="spa-fallback"),
]
