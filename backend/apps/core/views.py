"""
Health and readiness probe views for container orchestration and uptime monitoring (Task A32).
"""

import uuid
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views import View

APP_VERSION = "1.0.0"


class HealthCheckView(View):
    """
    Liveness probe endpoint (GET /health/).
    Returns HTTP 200 {"status": "ok", "version": "<version>"} without touching any external dependencies.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        return JsonResponse(
            {
                "status": "ok",
                "version": APP_VERSION,
            },
            status=200,
        )


class ReadinessCheckView(View):
    """
    Readiness probe endpoint (GET /ready/).
    Probes core database (SELECT 1), Redis cache, Celery message broker, and prediction registry.
    Returns HTTP 200 when database is healthy. Returns HTTP 503 only when the database is unavailable.
    Never leaks credentials, hostnames, or raw exception strings.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        # 1. Probe Core PostgreSQL Database
        db_healthy = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if not row or row[0] != 1:
                    db_healthy = False
        except Exception:
            db_healthy = False

        if not db_healthy:
            return JsonResponse(
                {
                    "status": "not_ready",
                    "failed": ["database"],
                },
                status=503,
            )

        # 2. Probe Redis Cache
        cache_status = "ok"
        try:
            probe_key = f"readiness_probe_{uuid.uuid4().hex[:8]}"
            cache.set(probe_key, "1", timeout=5)
            if cache.get(probe_key) != "1":
                cache_status = "unavailable"
            else:
                cache.delete(probe_key)
        except Exception:
            cache_status = "unavailable"

        # 3. Probe Celery Redis Broker
        broker_status = "ok"
        try:
            broker_url = getattr(settings, "CELERY_BROKER_URL", "")
            if broker_url and broker_url.startswith("redis"):
                import redis

                client = redis.Redis.from_url(
                    broker_url, socket_timeout=1.0, socket_connect_timeout=1.0
                )
                if not client.ping():
                    broker_status = "unavailable"
            elif not broker_url:
                broker_status = "unavailable"
        except Exception:
            broker_status = "unavailable"

        # 4. Probe Machine Learning Model Registry
        predictions_status = "available"
        try:
            from predictions.models import ModelVersion

            if not ModelVersion.objects.filter(is_active=True).exists():
                predictions_status = "unavailable"
        except Exception:
            predictions_status = "unavailable"

        return JsonResponse(
            {
                "status": "ready",
                "database": "ok",
                "cache": cache_status,
                "broker": broker_status,
                "predictions": predictions_status,
            },
            status=200,
        )
