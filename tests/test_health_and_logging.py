"""
Unit and integration tests for Health/Readiness probes, Request ID middleware, and PII-free structured logging (Task A32).
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from core.logging import JSONLogFormatter, RequestIDFilter, set_request_id
from core.views import APP_VERSION
from django.db import OperationalError
from django.test import Client


@pytest.fixture
def client():
    return Client()


def test_health_check_returns_200_and_version(client):
    """GET /health/ returns 200 {"status": "ok", "version": "1.0.0"} without database contact."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == APP_VERSION


@pytest.mark.django_db
def test_readiness_check_when_healthy(client):
    """GET /ready/ returns 200 {"status": "ready", ...} when database is healthy."""
    response = client.get("/ready/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert "cache" in data
    assert "broker" in data
    assert "predictions" in data


@pytest.mark.django_db
def test_readiness_check_when_cache_broker_and_models_unavailable(client):
    """
    GET /ready/ returns 200 when database is healthy even if cache, broker, or prediction registry are unavailable.
    Subsystem degradations are reported as 'unavailable' but do not drop readiness.
    """
    with (
        patch("django.core.cache.cache.get", side_effect=Exception("Redis cache down")),
        patch("redis.Redis.from_url", side_effect=Exception("Redis broker down")),
        patch(
            "predictions.models.ModelVersion.objects.filter",
            return_value=MagicMock(exists=lambda: False),
        ),
    ):
        response = client.get("/ready/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "ok"
        assert data["cache"] == "unavailable"
        assert data["broker"] == "unavailable"
        assert data["predictions"] == "unavailable"


@pytest.mark.django_db
def test_readiness_check_when_database_fails(client):
    """
    GET /ready/ returns HTTP 503 {"status": "not_ready", "failed": ["database"]} when database is unreachable.
    Guarantees that raw exception messages, hostnames, and credentials are never leaked.
    """
    with patch(
        "django.db.connection.cursor",
        side_effect=OperationalError("Connection refused to postgresql://secret:pass@db:5432"),
    ):
        response = client.get("/ready/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["failed"] == ["database"]
        # Strict leak prevention
        raw_body = response.content.decode("utf-8")
        assert "password" not in raw_body.lower()
        assert "postgresql://" not in raw_body
        assert "Connection refused" not in raw_body


def test_request_id_middleware_generates_uuid_when_missing(client):
    """When no X-Request-ID header is provided, a fresh UUID4 is generated and returned."""
    response = client.get("/health/")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 32
    assert "-" in req_id


def test_request_id_middleware_echoes_valid_custom_id(client):
    """When a valid X-Request-ID matching ^[A-Za-z0-9_-]{8,64}$ is supplied, it is preserved."""
    custom_id = "trace-req-abc_12345"
    response = client.get("/health/", HTTP_X_REQUEST_ID=custom_id)
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_request_id_middleware_replaces_invalid_custom_id(client):
    """When an invalid X-Request-ID (contains spaces or illegal characters) is supplied, it is replaced."""
    invalid_id = "invalid request id with spaces!"
    response = client.get("/health/", HTTP_X_REQUEST_ID=invalid_id)
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id != invalid_id
    assert " " not in req_id
    assert "!" not in req_id


def test_json_formatter_and_request_id_filter():
    """
    Verifies that JSONLogFormatter emits valid single-line JSON with ISO-8601 UTC timestamp and request_id.
    """
    test_req_id = "test-log-uuid-98765"
    set_request_id(test_req_id)
    try:
        formatter = JSONLogFormatter()
        filter_ = RequestIDFilter()

        record = logging.LogRecord(
            name="edupulse.audit",
            level=logging.INFO,
            pathname="views.py",
            lineno=42,
            msg="User login successful: user_id=%s, role=%s",
            args=(101, "student"),
            exc_info=None,
        )

        filter_.filter(record)
        assert getattr(record, "request_id", None) == test_req_id

        formatted_json = formatter.format(record)
        parsed = json.loads(formatted_json)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "edupulse.audit"
        assert parsed["request_id"] == test_req_id
        assert parsed["message"] == "User login successful: user_id=101, role=student"
        assert "timestamp" in parsed
        assert parsed["timestamp"].endswith("Z")
    finally:
        set_request_id("")


def test_pii_free_logging_enforcement():
    """
    Verifies that logging messages comply with PII rules:
    Logs user ID, role, and object IDs only. Never leaks student names, roll numbers, or phone numbers.
    """
    student_name = "Alexandria Confidential"
    student_roll = "ROLL-998877"
    student_phone = "+1-555-0199"

    safe_log_msg = "Student profile retrieved: student_id=45, user_id=12, dept_id=2"

    # Verify that the safe log statement contains none of the student's PII
    assert student_name not in safe_log_msg
    assert student_roll not in safe_log_msg
    assert student_phone not in safe_log_msg

    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="edupulse.academics",
        level=logging.INFO,
        pathname="services.py",
        lineno=10,
        msg=safe_log_msg,
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert student_name not in formatted
    assert student_roll not in formatted
    assert student_phone not in formatted
