"""
Celery background tasks for EduPulse Analytics Domain.
"""

import logging
from typing import Any, Dict
from celery import shared_task

from academics.models import Batch, Course, Department, School
from analytics.selectors import ScopeContext, get_analytics_overview
from analytics.serializers import AnalyticsOverviewSerializer
from api.caching import (
    get_analytics_cache_version,
    make_analytics_cache_key,
    safe_cache_set,
)

logger = logging.getLogger(__name__)


@shared_task(
    name="analytics.warm_cache",
    bind=True,
    acks_late=True,
    soft_time_limit=300,
    time_limit=330,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def warm_analytics_cache(self) -> Dict[str, Any]:
    """
    Periodic task to pre-compute and warm analytics caches for common institutional scopes:
    - University-wide overview
    - School-level overviews
    - Department-level overviews

    Idempotent and safe to run on beat schedule. Zero student PII handled.
    """
    task_id = getattr(getattr(self, "request", None), "id", "local")
    logger.info("Starting task analytics.warm_cache [id=%s]", task_id)

    version = get_analytics_cache_version()
    warmed_count = 0
    error_count = 0

    # 1. Warm University-wide Scope
    try:
        uni_scope = ScopeContext(
            user=None,
            role="ADMIN",
            scope_level="university",
            is_university_wide=True,
            allowed_school_ids=set(),
            allowed_department_ids=set(),
            allowed_course_ids=set(),
            allowed_batch_ids=set(),
            allowed_subject_ids=set(),
        )
        data = get_analytics_overview(uni_scope, {})
        serializer = AnalyticsOverviewSerializer(data)
        cache_key = make_analytics_cache_key("overview", uni_scope, {})
        safe_cache_set(cache_key, serializer.data, version=version)
        warmed_count += 1
    except Exception as e:
        logger.error("Failed warming university analytics cache: %s", e)
        error_count += 1

    # 2. Warm School Scopes
    schools = School.objects.all()
    for school in schools:
        try:
            school_scope = ScopeContext(
                user=None,
                role="DEAN",
                scope_level="school",
                is_university_wide=False,
                allowed_school_ids={school.id},
                allowed_department_ids=set(
                    Department.objects.filter(school=school).values_list("id", flat=True)
                ),
                allowed_course_ids=set(
                    Course.objects.filter(department__school=school).values_list("id", flat=True)
                ),
                allowed_batch_ids=set(
                    Batch.objects.filter(course__department__school=school).values_list(
                        "id", flat=True
                    )
                ),
                allowed_subject_ids=set(),
            )
            data = get_analytics_overview(school_scope, {})
            serializer = AnalyticsOverviewSerializer(data)
            cache_key = make_analytics_cache_key("overview", school_scope, {})
            safe_cache_set(cache_key, serializer.data, version=version)
            warmed_count += 1
        except Exception as e:
            logger.error("Failed warming school analytics cache [school_id=%s]: %s", school.id, e)
            error_count += 1

    # 3. Warm Department Scopes
    departments = Department.objects.select_related("school").all()
    for dept in departments:
        try:
            dept_scope = ScopeContext(
                user=None,
                role="HOD",
                scope_level="department",
                is_university_wide=False,
                allowed_school_ids={dept.school_id} if dept.school_id else set(),
                allowed_department_ids={dept.id},
                allowed_course_ids=set(
                    Course.objects.filter(department=dept).values_list("id", flat=True)
                ),
                allowed_batch_ids=set(
                    Batch.objects.filter(course__department=dept).values_list("id", flat=True)
                ),
                allowed_subject_ids=set(),
            )
            data = get_analytics_overview(dept_scope, {})
            serializer = AnalyticsOverviewSerializer(data)
            cache_key = make_analytics_cache_key("overview", dept_scope, {})
            safe_cache_set(cache_key, serializer.data, version=version)
            warmed_count += 1
        except Exception as e:
            logger.error("Failed warming department analytics cache [dept_id=%s]: %s", dept.id, e)
            error_count += 1

    logger.info(
        "analytics.warm_cache finished [warmed=%d, errors=%d]",
        warmed_count,
        error_count,
    )
    return {
        "status": "success" if error_count == 0 else "partial_success",
        "warmed_scopes": warmed_count,
        "errors": error_count,
    }
