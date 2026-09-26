"""
E2E Test: Student Journey & Reactive Habit Tracking.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_student_habit_checkin_and_results_flow(e2e_page, live_server, e2e_seed_data):
    """
    Verify complete student journey:
    1. Student logs in.
    2. Submits a study habit check-in.
    3. Checks habit history updates immediately.
    4. Views published semester results and marks breakdown.
    """
    login_via_ui(e2e_page, live_server, "e2e_student", "StudentPass@123")

    # 1. Habit Check-in Form
    e2e_page.goto(f"{live_server.url}/app/student/habits")
    e2e_page.wait_for_selector("#hours-studied-input", state="visible")

    e2e_page.fill("#hours-studied-input", "5.5")
    e2e_page.fill("#sleep-hours-input", "8.0")
    e2e_page.fill("#exercise-input", "1.0")
    e2e_page.select_option("#motivation-select", "High")
    e2e_page.fill("#notes-input", "Studied SQL indexing and query optimization.")

    e2e_page.click("button:has-text('Save Check-In')")

    # Assert feedback message and immediate table appearance
    e2e_page.wait_for_selector("text=Habit check-in recorded successfully!", timeout=8000)
    assert e2e_page.locator("td:has-text('5.5')").is_visible()
    assert e2e_page.locator("td:has-text('High')").is_visible()

    # 2. Results Flow
    e2e_page.goto(f"{live_server.url}/app/student/results")
    e2e_page.wait_for_selector("text=Academic Performance Records", state="visible")
    e2e_page.wait_for_selector("text=Database Management Systems", timeout=8000)
    assert e2e_page.locator("text=CS301").is_visible()
    assert e2e_page.locator("text=A+").is_visible()
