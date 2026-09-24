"""
Tests for role dashboards, Rule-of-3 KPIs, teacher internal marks entry, and admin actions.
Ported from legacy scripts/test_dashboard_suite.py to pytest using model factories.
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse
from django.contrib.messages.storage.fallback import FallbackStorage
from academics.admin import SemesterResultAdmin
from academics.models import InternalAssessment, SemesterResult
from tests.factories import make_university, SemesterResultFactory


@pytest.mark.django_db
def test_hierarchical_role_dashboards_render_rule_of_three_kpis(client):
    """
    Verify that each institutional role can access their dashboard (HTTP 200)
    and that the rendered template contains the Rule-of-3 KPI layout.
    """
    tree = make_university(students_per_batch=3)
    
    test_users = [
        tree["students"][0].user,
        tree["teachers"][0].user,
        tree["hod"],
        tree["dean"],
        tree["executives"]["vc"],
        tree["executives"]["admin"],
    ]

    for user in test_users:
        client.force_login(user)
        response = client.get(reverse("home"))
        assert response.status_code == 200, f"Dashboard failed for {user.role}: status {response.status_code}"
        content = response.content.decode("utf-8")
        assert "grid-kpi-3" in content, f"Grid 3 KPIs not found in HTML for role {user.role}"
        assert "kpi-card" in content, f"KPI cards missing for role {user.role}"


@pytest.mark.django_db
def test_teacher_internal_marks_get_and_inline_submission(client):
    """
    Verify teacher marks portal:
    1. GET portal returns HTTP 200.
    2. POST inline marks entry creates InternalAssessment and redirects (HTTP 302).
    """
    tree = make_university(students_per_batch=3)
    teacher_user = tree["teachers"][0].user
    assignment = tree["assignments"][0]
    student = tree["students"][0]

    client.force_login(teacher_user)

    # 1. GET view
    url = f"{reverse('teacher_internal_marks')}?assignment={assignment.id}"
    get_resp = client.get(url)
    assert get_resp.status_code == 200

    # 2. POST inline marks entry
    post_data = {
        "title": "Unit Test 1 - Automated",
        "assessment_type": "QUIZ",
        "max_marks": "25.0",
        f"marks_{student.id}": "22.5",
    }
    post_resp = client.post(url, post_data)
    assert post_resp.status_code == 302, f"Expected redirect 302, got {post_resp.status_code}"

    created_record = InternalAssessment.objects.filter(
        student=student, subject=assignment.subject, title="Unit Test 1 - Automated"
    ).first()
    assert created_record is not None, "InternalAssessment record was not created"
    assert created_record.marks_obtained == 22.5
    assert created_record.max_marks == 25.0


@pytest.mark.django_db
def test_teacher_internal_marks_csv_bulk_upload(client):
    """
    Verify teacher marks portal accepts CSV file uploads and creates assessment records.
    """
    tree = make_university(students_per_batch=3)
    teacher_user = tree["teachers"][0].user
    assignment = tree["assignments"][0]
    student = tree["students"][0]

    client.force_login(teacher_user)
    url = f"{reverse('teacher_internal_marks')}?assignment={assignment.id}"

    csv_content = f"roll_no,marks\n{student.roll_no},24.0\n"
    csv_file = SimpleUploadedFile("marks.csv", csv_content.encode("utf-8"), content_type="text/csv")
    post_data = {
        "title": "CSV Midterm Upload",
        "assessment_type": "MIDTERM",
        "max_marks": "30.0",
        "csv_file": csv_file,
    }

    resp = client.post(url, post_data)
    assert resp.status_code == 302, f"Expected redirect 302, got {resp.status_code}"

    csv_record = InternalAssessment.objects.filter(
        student=student, subject=assignment.subject, title="CSV Midterm Upload"
    ).first()
    assert csv_record is not None, "CSV assessment record was not created"
    assert csv_record.marks_obtained == 24.0
    assert csv_record.max_marks == 30.0


@pytest.mark.django_db
def test_admin_publish_and_revert_actions():
    """
    Verify Django admin actions for bulk result publishing and reverting to draft.
    """
    tree = make_university(students_per_batch=2)
    admin_user = tree["executives"]["admin"]
    student = tree["students"][0]
    
    sem_res = SemesterResult.objects.filter(student=student, semester=1).first()
    assert sem_res is not None
    sem_res.is_published = False
    sem_res.save()

    admin_instance = SemesterResultAdmin(SemesterResult, AdminSite())
    queryset = SemesterResult.objects.filter(id=sem_res.id)

    factory = RequestFactory()
    req = factory.get("/")
    req.user = admin_user
    setattr(req, "session", {})
    setattr(req, "_messages", FallbackStorage(req))

    # Test publish
    admin_instance.publish_final_results(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published is True

    # Test revert to draft
    admin_instance.revert_to_draft(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published is False
