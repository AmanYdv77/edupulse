"""
E2E Test: Executive Workflow & Student Privacy Guarantees.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_executive_analytics_and_student_privacy(e2e_page, live_server, e2e_seed_data):
    """
    Verify Vice Chancellor / Registrar executive journey:
    1. Executive logs in.
    2. Navigates to institutional analytics at /app/analytics.
    3. Verifies high-level KPIs, differential privacy breakdown, and longitudinal trends render.
    4. Asserts that ZERO student names, roll numbers, or personal identifying information
       are present anywhere in the DOM / rendered text.
    """
    login_via_ui(e2e_page, live_server, "e2e_vc", "VcPass@123")

    e2e_page.goto(f"{live_server.url}/app/analytics")
    e2e_page.wait_for_selector("text=Institutional Academic Analytics", state="visible")

    # Verify high-level institutional KPI cards
    e2e_page.wait_for_selector("text=Total Students", timeout=8000)
    assert e2e_page.locator("text=Overall Pass Rate").is_visible()
    assert e2e_page.locator("text=Performance Breakdown & Comparison").is_visible()
    assert e2e_page.locator("text=Longitudinal Performance Trends").is_visible()

    # Verify Privacy Policy indicator in subtitle
    assert e2e_page.locator("text=Suppressed per privacy policy").is_visible()

    # STRICT PII PRIVACY AUDIT: Ensure no student names or roll numbers are present in DOM
    page_text = e2e_page.inner_text("body")
    assert "Aarav" not in page_text
    assert "Sharma" not in page_text
    assert "E2E-CS-001" not in page_text
