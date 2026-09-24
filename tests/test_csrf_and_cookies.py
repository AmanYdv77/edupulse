import os
import subprocess
import sys
from pathlib import Path
import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, JsonResponse
from django.test import Client, RequestFactory
from accounts.middleware import NoCacheAuthenticatedMiddleware
from tests.factories import make_university


@pytest.mark.django_db
class TestCsrfAndCookieHardening:
    """Verifies CSRF token flow, cookie security, and bfcache prevention."""

    def test_base_html_has_no_csrf_sync_script(self):
        """Ensure the fragile inline CSRF synchronizer script is completely removed."""
        base_html_path = Path(settings.BASE_DIR) / "templates" / "base.html"
        content = base_html_path.read_text(encoding="utf-8")

        assert "Automatic CSRF Token Synchronizer" not in content
        assert "getActiveCsrfCookie" not in content
        assert "syncCsrfInputs" not in content
        # Ensure no inline script searches for csrfmiddlewaretoken inputs
        assert "input[name=\"csrfmiddlewaretoken\"]" not in content

    def test_base_settings_security_flags(self):
        """Ensure base security settings adhere to hardened defaults."""
        assert settings.CSRF_COOKIE_HTTPONLY is True
        assert settings.SESSION_COOKIE_HTTPONLY is True
        assert settings.SESSION_COOKIE_SAMESITE == "Lax"
        assert settings.CSRF_COOKIE_SAMESITE == "Lax"
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert settings.X_FRAME_OPTIONS == "DENY"
        assert settings.SECURE_REFERRER_POLICY == "same-origin"

    def test_authenticated_html_response_prevents_bfcache(self, client: Client):
        """
        Authenticated HTML responses must have 'Cache-Control: no-store, private'
        to prevent browsers from caching forms in the back/forward cache (bfcache).
        """
        uni = make_university(students_per_batch=1)
        student_user = uni["students"][0].user
        client.force_login(student_user)

        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")

        cache_control = response.headers.get("Cache-Control", "")
        assert "no-store" in cache_control
        assert "private" in cache_control
        assert response.headers.get("Pragma") == "no-cache"

    def test_nocache_middleware_logic(self, rf: RequestFactory):
        """Unit test NoCacheAuthenticatedMiddleware for various request/response types."""
        uni = make_university(students_per_batch=1)
        student_user = uni["students"][0].user

        middleware = NoCacheAuthenticatedMiddleware(
            get_response=lambda r: HttpResponse("<html><body>Dashboard</body></html>", content_type="text/html")
        )

        # 1. Authenticated user + text/html -> sets headers
        req_auth = rf.get("/dashboard/")
        req_auth.user = student_user
        res_auth = middleware(req_auth)
        assert res_auth["Cache-Control"] == "no-store, private"
        assert res_auth["Pragma"] == "no-cache"

        # 2. Anonymous user + text/html -> headers untouched
        req_anon = rf.get("/public/")
        req_anon.user = AnonymousUser()
        res_anon = middleware(req_anon)
        assert "Cache-Control" not in res_anon
        assert "Pragma" not in res_anon

        # 3. Authenticated user + application/json -> headers untouched
        json_middleware = NoCacheAuthenticatedMiddleware(
            get_response=lambda r: JsonResponse({"status": "ok"})
        )
        res_json = json_middleware(req_auth)
        assert "Cache-Control" not in res_json

    def test_form_submission_with_standard_csrf_token(self):
        """Standard Django CSRF token flow functions properly without client-side script."""
        # Use an enforcing client to verify CSRF validation
        csrf_client = Client(enforce_csrf_checks=True)
        get_res = csrf_client.get("/accounts/login/")
        assert get_res.status_code == 200

        # Extract CSRF token from the cookie set by the view
        csrf_cookie = csrf_client.cookies.get(settings.CSRF_COOKIE_NAME)
        assert csrf_cookie is not None

        # POST login with invalid credentials to test CSRF token is accepted (not 403 Forbidden)
        post_res = csrf_client.post(
            "/accounts/login/",
            {
                "username": "nonexistent_user",
                "password": "wrong_password",
                "csrfmiddlewaretoken": csrf_cookie.value,
            },
        )
        # Form re-renders with 200 (invalid login), not 403 CSRF failure
        assert post_res.status_code == 200
        assert b"Forbidden" not in post_res.content
        assert post_res.status_code != 403

    def test_prod_check_deploy_has_zero_warnings(self):
        """Verify python manage.py check --deploy passes with 0 warnings on prod settings."""
        env = os.environ.copy()
        env["DJANGO_SECRET_KEY"] = "c8f7e2a9b4d1e6f3a8b2c5d7e1f4a9b3c6d8e2f5a7b1c4d9e3f6a8b2c5d7e1f4"
        env["DJANGO_DEBUG"] = "False"
        env["DATABASE_URL"] = "postgres://postgres:postgres@localhost:55432/edupulse_prod"
        env["DJANGO_ALLOWED_HOSTS"] = "edupulse.example.com"

        manage_py = Path(settings.BASE_DIR) / "manage.py"
        res = subprocess.run(
            [sys.executable, str(manage_py), "check", "--deploy", "--settings=resultplatform.settings.prod"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"check --deploy failed: {res.stderr}\n{res.stdout}"
        assert "System check identified no issues" in res.stdout
