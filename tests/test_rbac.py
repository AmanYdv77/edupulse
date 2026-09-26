"""
Role-Based Access Control (RBAC) and Organizational Hierarchy Scoping Tests.
Tests academic and institutional scoping across institutional roles.
"""
import pytest
from academics.models import Result
from academics.selectors import scoped_results_for
from tests.factories import make_university


@pytest.mark.django_db
def test_scoped_results_for_teacher():
    """A teacher must only see results for students in subjects they teach."""
    tree = make_university(students_per_batch=4)
    teacher1_user = tree["teachers"][0].user
    teacher2_user = tree["teachers"][1].user

    t1_results, label1 = scoped_results_for(teacher1_user)
    assert t1_results.count() == 4
    for res in t1_results:
        assert res.teacher == tree["teachers"][0]

    t2_results, label2 = scoped_results_for(teacher2_user)
    assert t2_results.count() == 4
    for res in t2_results:
        assert res.teacher == tree["teachers"][1]


@pytest.mark.django_db
def test_scoped_results_for_hod():
    """An HOD must only see results for courses/departments within their department."""
    tree = make_university(students_per_batch=4)
    hod_user = tree["hod"]

    results, label = scoped_results_for(hod_user)
    # 4 students * 2 subjects = 8 results in this department
    assert results.count() == 8
    for res in results:
        assert res.subject.course.department == tree["department"]


@pytest.mark.django_db
def test_scoped_results_for_dean():
    """A Dean must only see results within their school."""
    tree = make_university(students_per_batch=4)
    dean_user = tree["dean"]

    results, label = scoped_results_for(dean_user)
    assert results.count() == 8
    for res in results:
        assert res.subject.course.department.school == tree["school"]


@pytest.mark.django_db
def test_scoped_results_for_student():
    """A student must have no access to bulk scoped results."""
    tree = make_university(students_per_batch=2)
    student_user = tree["students"][0].user

    results, label = scoped_results_for(student_user)
    assert results.count() == 0
    assert label == "No access"


@pytest.mark.django_db
def test_scoped_results_for_executives():
    """Executives (VC, Registrar, Controller of Exams, System Admin) see all university results."""
    tree = make_university(students_per_batch=3)
    # Total results = 3 students * 2 subjects = 6
    total_count = Result.objects.count()

    for role_key in ("vc", "registrar", "controller", "admin"):
        exec_user = tree["executives"][role_key]
        results, label = scoped_results_for(exec_user)
        assert results.count() == total_count
        assert label == "Entire University"
