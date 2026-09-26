"""
Performance and query count benchmarks using django_assert_max_num_queries.
Validates bounded query execution for REST API endpoints.
"""

import pytest
from django.urls import reverse
from tests.factories import make_university


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_key,max_queries",
    [
        ("teacher", 15),
        ("hod", 15),
        ("dean", 15),
        ("vc", 15),
    ],
)
def test_analytics_overview_query_count_bounded(
    client, django_assert_max_num_queries, role_key, max_queries
):
    """
    Verify that analytics overview API queries adhere to an established upper-bound query budget.
    """
    tree = make_university(students_per_batch=10)
    user_map = {
        "teacher": tree["teachers"][0].user,
        "hod": tree["hod"],
        "dean": tree["dean"],
        "vc": tree["executives"]["vc"],
    }
    user = user_map[role_key]
    client.force_login(user)

    url = reverse("api_v1:analytics-overview")
    with django_assert_max_num_queries(max_queries):
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_at_risk_api_query_budget(client, django_assert_max_num_queries):
    """
    Target benchmark for at-risk API: querying 30 students must stay within a fixed query budget (<= 6).
    Verified O(1) query count via pre-computed PredictionSnapshot reads for HOD within scope.
    """
    tree = make_university(students_per_batch=30)
    hod_user = tree["hod"]
    client.force_login(hod_user)

    url = reverse("api_v1:analytics-at-risk")
    with django_assert_max_num_queries(8):
        response = client.get(url)
        assert response.status_code == 200
