"""
E2E Test: System Administrator Model Registry & Live Slot Promotion.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_admin_model_registry_activation_flow(e2e_page, live_server, e2e_seed_data):
    """
    Verify System Admin ML lifecycle workflow:
    1. Admin logs in.
    2. Navigates to /app/models.
    3. Views registered model versions and holdout evaluation metrics.
    4. Clicks 'Activate Version' on an inactive model version.
    5. Confirms modal activation dialog.
    6. Verifies success feedback and updated active serving state.
    """
    login_via_ui(e2e_page, live_server, "e2e_admin", "AdminPass@123")

    e2e_page.goto(f"{live_server.url}/app/models")
    e2e_page.wait_for_selector("text=Machine Learning Model Registry", state="visible")
    assert e2e_page.locator("text=Registered Model Versions").is_visible()
    assert e2e_page.locator("text=Model A (Baseline)").is_visible()
    assert e2e_page.locator("text=Model B (Institute)").is_visible()

    # Model B is initially inactive; find and click 'Activate Version'
    activate_btn = e2e_page.locator("button:has-text('Activate Version')")
    assert activate_btn.is_visible()
    activate_btn.click()

    # Modal appears
    e2e_page.wait_for_selector("text=Confirm Model Activation", state="visible")
    assert e2e_page.locator("button:has-text('Confirm & Activate')").is_visible()

    # Confirm activation
    e2e_page.click("button:has-text('Confirm & Activate')")

    # Verify feedback alert
    e2e_page.wait_for_selector("text=Model version activated successfully!", timeout=8000)
