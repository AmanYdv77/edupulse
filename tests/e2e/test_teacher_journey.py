"""
E2E Test: Teacher Journey, Internal Marks Assessment & At-Risk Roster.
"""

import pytest
from tests.e2e.conftest import login_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_teacher_classes_marks_entry_and_roster(e2e_page, live_server, e2e_seed_data):
    """
    Verify complete teacher workflow:
    1. Teacher logs in.
    2. Inspects assigned teaching sections at /app/classes.
    3. Records continuous internal marks assessment at /app/marks.
    4. Inspects flagged students at /app/roster.
    """
    login_via_ui(e2e_page, live_server, "e2e_teacher", "TeacherPass@123")

    # 1. My Classes
    e2e_page.goto(f"{live_server.url}/app/classes")
    e2e_page.wait_for_selector("text=Database Management Systems", state="visible")
    assert e2e_page.locator("button:has-text('CS301')").is_visible()
    assert e2e_page.locator("button:has-text('2024-CSE-A')").is_visible()

    # 2. Internal Marks Entry
    e2e_page.goto(f"{live_server.url}/app/marks")
    e2e_page.wait_for_selector("#assignment-select", state="visible")

    # Select assignment
    e2e_page.select_option("#assignment-select", index=1)

    student_id = str(e2e_seed_data["student"].id)
    student_inputs = e2e_page.locator("input[placeholder*='Student ID']")
    marks_inputs = e2e_page.locator("input[placeholder*='Marks']")

    student_inputs.first.fill(student_id)
    marks_inputs.first.fill("28.5")

    e2e_page.click("button:has-text('Submit Assessment Marks')")
    e2e_page.wait_for_selector("text=Successfully updated", timeout=8000)

    # 3. At-Risk Roster
    e2e_page.goto(f"{live_server.url}/app/roster")
    e2e_page.wait_for_selector("text=Early Warning & At-Risk Roster", state="visible")
    assert e2e_page.locator("button:has-text('Export CSV')").is_visible()
