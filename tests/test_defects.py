"""
Known defects recorded as strict xfail tests per EduPulse Playbook Task A8 requirements.
These tests capture the DESIRED security behavior and MUST fail under current code,
marking them as strict xfail. They will pass once resolved in Task A10.
"""
import pytest
from django.urls import reverse
from tests.factories import make_university, HODUserFactory


@pytest.mark.django_db
@pytest.mark.xfail(strict=True, reason="fixed in A10")
def test_student_cohort_api_access_forbidden(client):
    """
    Defect 1: A student calling /analytics/api/cohort-query/ must receive HTTP 403 Forbidden.
    Currently, the view only requires @login_required, permitting student access (HTTP 200).
    """
    tree = make_university(students_per_batch=2)
    student_user = tree["students"][0].user
    client.force_login(student_user)

    url = reverse("api_cohort_query")
    response = client.get(url)

    # DESIRED BEHAVIOR (A10): Access must be denied with HTTP 403
    assert response.status_code == 403, f"Expected HTTP 403 Forbidden, got {response.status_code}"


@pytest.mark.django_db
@pytest.mark.xfail(strict=True, reason="fixed in A10")
def test_hod_without_department_sees_no_other_department_data(client):
    """
    Defect 2: An HOD without an assigned department must not be shown data from other departments.
    Currently, analytics_hub falls back to Department.objects.first(), leaking other departments.
    """
    from academics.models import Department
    tree = make_university(students_per_batch=2)
    unassigned_hod = HODUserFactory.create(department=None, school=None)
    client.force_login(unassigned_hod)

    url = reverse("analytics_hub")
    response = client.get(url)

    # DESIRED BEHAVIOR (A10): Must not leak data from other departments
    first_dept = Department.objects.first()
    first_course = first_dept.courses.first() if first_dept else None
    assert first_course is not None
    content = response.content.decode("utf-8")
    assert first_course.code not in content, "Unassigned HOD was shown data from Department.objects.first()"



@pytest.mark.django_db
@pytest.mark.xfail(strict=True, reason="fixed in A10")
def test_non_teacher_staff_cannot_list_assignments(client):
    """
    Defect 3: A staff user without a teacher profile must not list university teaching assignments.
    Currently, teacher_internal_marks falls back to TeachingAssignment.objects.all()[:10].
    """
    tree = make_university(students_per_batch=2)
    admin_user = tree["executives"]["admin"]  # is_staff=True, no teacher_profile
    client.force_login(admin_user)

    url = reverse("teacher_internal_marks")
    response = client.get(url)

    # DESIRED BEHAVIOR (A10): Access restricted with 403
    assert response.status_code == 403, f"Expected HTTP 403 Forbidden, got {response.status_code}"
