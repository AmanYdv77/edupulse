"""
E2E Test: HOD & Dean Scoped Analytics & Access Control.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_hod_scoped_analytics_and_unauthorized_routes(e2e_page, live_server, e2e_seed_data):
    """
    Verify HOD institutional analytics dashboard & access boundary:
    1. HOD logs in and accesses departmental analytics at /app/analytics.
    2. HOD attempts to access unauthorized system admin route /app/models and is denied.
    """
    login_via_ui(e2e_page, live_server, "e2e_hod", "HodPass@123")

    # 1. Scoped Analytics
    e2e_page.goto(f"{live_server.url}/app/analytics")
    e2e_page.wait_for_selector("text=Institutional Academic Analytics", state="visible")
    assert e2e_page.locator("text=Performance Breakdown & Comparison").is_visible()

    # 2. Unauthorized Route
    e2e_page.goto(f"{live_server.url}/app/models")
    # RouteGuard redirects to /app/unauthorized or shows access denied
    e2e_page.wait_for_selector("text=403", timeout=8000)
    assert e2e_page.locator("text=Access Denied").is_visible() or e2e_page.locator("text=403").is_visible()
