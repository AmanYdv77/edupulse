"""
Integration tests for Django Single Page Application (SPA) serving & Security Headers.

Verifies:
- /app/ endpoint serves frontend index.html with HTTP 200.
- Client-side routing subpaths (/app/student/results, /app/analytics, /app/unknown) fallback to index.html.
- SecurityHeadersMiddleware sets strict Content-Security-Policy (CSP) headers.
- X-Content-Type-Options: nosniff and Referrer-Policy: same-origin headers are present.
- Cache-Control is configured to prevent caching of the index.html entry point.
- Graceful degradation when frontend build artifacts are missing.
"""

from unittest.mock import patch
from pathlib import Path
import pytest
from django.test import Client


@pytest.mark.django_db
class TestSPAServingAndSecurityHeaders:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = Client()

    def test_spa_root_serves_html_and_csp_headers(self):
        """Verify /app/ returns 200 and injects strict Content-Security-Policy."""
        response = self.client.get("/app/")

        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]

        # Check Security Headers
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("Referrer-Policy") == "same-origin"
        assert "no-cache" in response.headers.get("Cache-Control", "")

    def test_spa_subroute_fallback(self):
        """Verify client-side subroutes under /app/* return index.html for SPA router dispatch."""
        response = self.client.get("/app/student/results")
        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        assert "Content-Security-Policy" in response.headers

        response_nested = self.client.get("/app/analytics/breakdown/deep/route")
        assert response_nested.status_code == 200
        assert "text/html" in response_nested["Content-Type"]

    def test_spa_missing_dist_fallback(self, monkeypatch, tmp_path):
        """When frontend/dist/index.html is missing, server returns informative fallback without crashing."""
        empty_dir = tmp_path / "empty_dist"
        empty_dir.mkdir(parents=True, exist_ok=True)

        with patch("backend.apps.core.spa.settings.FRONTEND_DIST_DIR", empty_dir):
            response = self.client.get("/app/")
            assert response.status_code == 200
            assert "text/html" in response["Content-Type"]
            assert "Content-Security-Policy" in response.headers
            assert b"Frontend distribution build not found" in response.content
