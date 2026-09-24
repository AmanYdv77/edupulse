"""
Tests for Multi-Tier Analytics Engine, statistical computations, and cohort query APIs.
Ported from legacy scripts/test_analytics_suite.py to pytest using model factories.
"""
import pytest
from django.urls import reverse
from academics.analytics_engine import (
    compute_cohort_deep_dive,
    get_student_analytics,
    get_teacher_analytics,
    get_hod_analytics,
    get_dean_analytics,
    get_executive_analytics,
)
from tests.factories import make_university


@pytest.mark.django_db
def test_statistical_cohort_deep_dive_engine():
    """
    Verify the statistical 5-number summary, average, pass rate, and 7-bin histogram.
    """
    make_university(students_per_batch=10)
    stats = compute_cohort_deep_dive()

    assert stats["total_count"] >= 10, "Cohort total count should include all active student records"
    assert len(stats["chart_data"]) == 7, "Histogram distribution must contain exactly 7 bins"
    assert "min_sgpa" in stats
    assert "q1_sgpa" in stats
    assert "median_sgpa" in stats
    assert "q3_sgpa" in stats
    assert "max_sgpa" in stats
    assert stats["min_sgpa"] <= stats["median_sgpa"] <= stats["max_sgpa"]
    assert 0 <= stats["pass_percentage"] <= 100


@pytest.mark.django_db
def test_student_self_reflection_analytics():
    """
    Verify student self-reflection computation (percentile, rank, standing, delta).
    """
    tree = make_university(students_per_batch=5)
    student = tree["students"][0]

    st_data = get_student_analytics(student)
    assert st_data["batch_size"] == 5
    assert 1 <= st_data["rank"] <= 5
    assert "percentile_rank" in st_data
    assert "batch_standing" in st_data
    assert "sgpa_delta" in st_data
    assert "trajectory_labels" in st_data


@pytest.mark.django_db
def test_stakeholder_analytics_engines():
    """
    Verify Teacher, HOD, Dean, and Executive analytics engines produce valid structures.
    """
    tree = make_university(students_per_batch=5)
    teacher = tree["teachers"][0]
    dept = tree["department"]
    school = tree["school"]

    # 1. Teacher Analytics
    tc_data = get_teacher_analytics(teacher)
    assert "assignments" in tc_data
    assert "scatter_points" in tc_data
    assert tc_data["assignments"].count() >= 1

    # 2. HOD Analytics
    hod_data = get_hod_analytics(dept)
    assert "bottlenecks" in hod_data
    assert "compliance_list" in hod_data

    # 3. Dean Analytics
    dean_data = get_dean_analytics(school)
    assert "dept_benchmarks" in dean_data
    assert "honors_count" in dean_data

    # 4. Executive Analytics
    exec_data = get_executive_analytics()
    assert "anomaly_flags" in exec_data
    assert "moderation_scatter" in exec_data
    assert "drafts_count" in exec_data


@pytest.mark.django_db
def test_analytics_hub_endpoint_status_across_roles(client):
    """
    Verify /analytics/ view renders HTTP 200 across stakeholder roles.
    """
    tree = make_university(students_per_batch=3)
    users_to_test = [
        tree["students"][0].user,
        tree["teachers"][0].user,
        tree["hod"],
        tree["dean"],
        tree["executives"]["vc"],
    ]

    for user in users_to_test:
        client.force_login(user)
        response = client.get(reverse("analytics_hub"))
        assert response.status_code == 200, f"Expected 200 for role {user.role}, got {response.status_code}"


@pytest.mark.django_db
def test_cohort_query_api_json_response(client):
    """
    Verify /analytics/api/cohort-query/ endpoint returns valid JSON with status 'success'.
    """
    tree = make_university(students_per_batch=4)
    staff_user = tree["executives"]["vc"]
    client.force_login(staff_user)

    url = reverse("api_cohort_query")
    response = client.get(url)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert "total_count" in json_data["data"]
