"""
E2E Test: Authentication, Security Headers & Login Hygiene.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_login_page_hygiene_and_csp_headers(e2e_page, live_server):
    """
    Verify login page does not leak any demo passwords, credentials tables,
    or autofill buttons, and sets strict Content-Security-Policy headers.
    """
    response = e2e_page.goto(f"{live_server.url}/app/login")

    assert response.status == 200
    csp_header = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp_header
    assert "frame-ancestors 'none'" in csp_header

    # Verify absence of leaked passwords or demo buttons
    page_text = e2e_page.inner_text("body")
    assert "Pass@" not in page_text
    assert "password123" not in page_text
    assert "pass1234" not in page_text
    assert "auto-fill" not in page_text.lower()
    assert e2e_page.locator("#username-input").is_visible()
    assert e2e_page.locator("#password-input").is_visible()


def test_student_login_and_navigation_capabilities(e2e_page, live_server, e2e_seed_data):
    """
    Verify Student logs in and receives capability-scoped navigation:
    sees My Dashboard, Results, Habit Check-In; does NOT see Classes, At-Risk Roster, or Model Registry.
    """
    login_via_ui(e2e_page, live_server, "e2e_student", "StudentPass@123")

    e2e_page.wait_for_selector(".app-sidebar", state="visible")

    # Allowed navigation
    assert e2e_page.locator("a:has-text('My Results')").is_visible()
    assert e2e_page.locator("a:has-text('Habit Check-In')").is_visible()

    # Forbidden navigation
    assert not e2e_page.locator("a:has-text('My Classes')").is_visible()
    assert not e2e_page.locator("a:has-text('At-Risk Roster')").is_visible()
    assert not e2e_page.locator("a:has-text('Model Registry')").is_visible()

    # Test Logout flow
    e2e_page.click("button:has-text('Sign Out')")
    e2e_page.wait_for_url(lambda u: "/app/login" in u, timeout=5000)
    assert e2e_page.locator("#username-input").is_visible()
