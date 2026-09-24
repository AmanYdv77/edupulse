"""
Performance and query count benchmarks using django_assert_max_num_queries.
Validates bounded query execution for dashboards and records at-risk page N+1 queries as xfail.
"""
import pytest
from django.urls import reverse
from tests.factories import make_university


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_key,max_queries",
    [
        ("student", 13),      # Baseline measured: 11
        ("teacher", 10),      # Baseline measured: 8
        ("hod", 15),          # Baseline measured: 12
        ("dean", 10),         # Baseline measured: 8
        ("vc", 35),           # Baseline measured: 16-26
        ("admin", 5),         # Baseline measured: 4


    ],
)
def test_dashboard_query_count_bounded(client, django_assert_max_num_queries, role_key, max_queries):
    """
    Verify that role dashboard rendering adheres to an established upper-bound query budget.
    """
    tree = make_university(students_per_batch=10)
    user_map = {
        "student": tree["students"][0].user,
        "teacher": tree["teachers"][0].user,
        "hod": tree["hod"],
        "dean": tree["dean"],
        "vc": tree["executives"]["vc"],
        "admin": tree["executives"]["admin"],
    }
    user = user_map[role_key]
    client.force_login(user)

    url = reverse("home")
    with django_assert_max_num_queries(max_queries):
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_at_risk_page_query_budget(client, django_assert_max_num_queries):
    """
    Target benchmark for at-risk page: rendering 30 students must stay within a fixed query budget (<= 4).
    Accounts for 2 Django session/auth middleware queries and 1 bounded snapshot query.
    Verified O(1) query count via pre-computed PredictionSnapshot reads.
    """
    tree = make_university(students_per_batch=30)
    teacher_user = tree["teachers"][0].user
    client.force_login(teacher_user)

    url = reverse("at_risk_students")
    with django_assert_max_num_queries(4):
        response = client.get(url)
        assert response.status_code == 200
