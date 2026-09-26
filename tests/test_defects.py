"""
Tests for security defects and role/scope authorization enforcement (Task A10 & REST API).
Verifies out-of-scope queries, post verification, and security logging without PII leakage.
"""

import logging
import pytest
from django.urls import reverse
from tests.factories import (
    make_university,
    HODUserFactory,
    DeanUserFactory,
    TeacherUserFactory,
    TeacherProfileFactory,
    TeachingAssignmentFactory,
)
from academics.models import Department, School, Batch


@pytest.mark.django_db
def test_student_cohort_api_access_forbidden(client):
    """
    Defect 1: A student calling faculty analytics endpoints must receive HTTP 403 Forbidden.
    """
    tree = make_university(students_per_batch=2)
    student_user = tree["students"][0].user
    client.force_login(student_user)

    url = reverse("api_v1:analytics-overview")
    response = client.get(url)

    assert response.status_code == 403, f"Expected HTTP 403 Forbidden, got {response.status_code}"


@pytest.mark.django_db
def test_hod_without_department_sees_no_other_department_data(client):
    """
    Defect 2: An HOD without an assigned department must not receive data from other departments.
    """
    tree = make_university(students_per_batch=2)
    unassigned_hod = HODUserFactory.create(department=None, school=None)
    client.force_login(unassigned_hod)

    url = reverse("api_v1:analytics-overview")
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 0, "Unassigned HOD was shown students from another department"


@pytest.mark.django_db
def test_dean_without_school_sees_no_other_school_data(client):
    """
    Verify a Dean without an assigned school sees a clean unassigned state without leaking other schools.
    """
    tree = make_university(students_per_batch=2)
    unassigned_dean = DeanUserFactory.create(school=None)
    client.force_login(unassigned_dean)

    url = reverse("api_v1:analytics-overview")
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 0, "Unassigned Dean was shown students from another school"


@pytest.mark.django_db
def test_non_teacher_staff_cannot_list_assignments(client):
    """
    Defect 3: A staff user without a teacher profile must not list teaching assignments.
    """
    tree = make_university(students_per_batch=2)
    admin_user = tree["executives"]["admin"]
    client.force_login(admin_user)

    url = reverse("api_v1:teaching-assignments")
    response = client.get(url)

    assert response.status_code == 403, f"Expected HTTP 403 Forbidden, got {response.status_code}"


@pytest.mark.django_db
def test_api_cohort_query_out_of_scope_returns_403(client):
    """
    Verify that an HOD querying an out-of-scope department receives HTTP 403.
    """
    from tests.factories import DepartmentFactory
    tree = make_university(students_per_batch=2)
    hod_user = tree["hod"]
    client.force_login(hod_user)

    other_dept = DepartmentFactory.create(school=tree["school"])

    url = reverse("api_v1:analytics-overview") + f"?department={other_dept.id}"
    response = client.get(url)

    assert response.status_code == 403, f"Expected HTTP 403 for out-of-scope department query, got {response.status_code}"


@pytest.mark.django_db
def test_teacher_cannot_post_marks_for_unassigned_class(client):
    """
    Verify that a teacher cannot submit marks for a teaching assignment that does not belong to them.
    """
    tree = make_university(students_per_batch=2)
    teacher_1 = tree["teachers"][0]
    teacher_2 = tree["teachers"][1]

    # Assignment belonging to teacher_2
    foreign_assignment = tree["assignments"][1]
    assert foreign_assignment.teacher == teacher_2

    client.force_login(teacher_1.user)

    url = reverse("api_v1:internal-marks")
    payload = {
        "subject_id": foreign_assignment.subject.id,
        "batch_id": foreign_assignment.batch.id,
        "marks": [
            {"student_id": tree["students"][0].id, "internal_marks": 20.0}
        ]
    }
    response = client.post(url, payload, content_type="application/json")

    assert response.status_code == 403, f"Expected HTTP 403 Forbidden, got {response.status_code}"


@pytest.mark.django_db
def test_denied_request_logs_warning_without_pii(client, caplog):
    """
    Verify that denied access attempts log a WARNING with user id, role, and path only (no PII).
    """
    tree = make_university(students_per_batch=2)
    student_user = tree["students"][0].user
    client.force_login(student_user)

    with caplog.at_level(logging.WARNING, logger="accounts.security"):
        url = reverse("api_v1:teaching-assignments")
        client.get(url)

    # Check log message
    warning_records = [r for r in caplog.records if r.name == "accounts.security" and r.levelname == "WARNING"]
    assert len(warning_records) >= 1
    log_msg = warning_records[0].getMessage()
    assert f"user_id={student_user.id}" in log_msg
    assert "role=STUDENT" in log_msg
    assert f"path={url}" in log_msg

    # Confirm absence of PII
    assert student_user.username not in log_msg or student_user.username == str(student_user.id)
    assert student_user.first_name not in log_msg
    assert student_user.last_name not in log_msg
