"""
Redis and In-Memory Caching & $O(1)$ Invalidation Module for EduPulse.

Provides deterministic cache key generation, generation version tracking,
fault-tolerant safe get/set wrappers, and event-driven invalidation helpers.
"""

import hashlib
import logging
from typing import Any, Dict, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

ANALYTICS_VERSION_KEY = "edupulse:version:analytics"
STUDENT_VERSION_PREFIX = "edupulse:version:student"
MODEL_VERSION_KEY = "edupulse:version:model"

DEFAULT_ANALYTICS_CACHE_TTL = 300  # 5 minutes
DEFAULT_PREDICTION_CACHE_TTL = 600  # 10 minutes


def _hash_params(params: Optional[Dict[str, Any]]) -> str:
    """Generate deterministic MD5 hash for query parameters or scope dictionaries."""
    if not params:
        return "none"
    try:
        clean_items = []
        for k, v in sorted(params.items()):
            if v is not None and v != "":
                clean_items.append(f"{k}={v}")
        if not clean_items:
            return "none"
        raw_str = "&".join(clean_items)
        return hashlib.md5(raw_str.encode("utf-8")).hexdigest()[:12]
    except Exception as e:
        logger.warning("Error hashing cache params: %s", e)
        return "fallback"


def make_analytics_cache_key(
    endpoint: str,
    scope: Any,
    scope_id_or_params: Optional[Any] = None,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Constructs a deterministic cache key for analytics endpoints.
    Accepts either (endpoint, ScopeContext, params) or (endpoint, scope_level, scope_id, params).
    Format: analytics:{endpoint}:{scope_level}:{scope_identifier}:{params_hash}
    Zero PII is embedded in keys.
    """
    if hasattr(scope, "scope_level"):
        # Passed a ScopeContext object
        s_level = getattr(scope, "scope_level", "unknown")
        if getattr(scope, "is_university_wide", False):
            s_id = "all"
        elif getattr(scope, "allowed_department_ids", None):
            depts = sorted(list(scope.allowed_department_ids))
            s_id = f"dept_{'_'.join(map(str, depts))}"
        elif getattr(scope, "allowed_school_ids", None):
            schools = sorted(list(scope.allowed_school_ids))
            s_id = f"sch_{'_'.join(map(str, schools))}"
        else:
            s_id = f"u_{getattr(getattr(scope, 'user', None), 'id', 0)}"

        param_dict = scope_id_or_params if isinstance(scope_id_or_params, dict) else params
    else:
        s_level = str(scope)
        s_id = str(scope_id_or_params) if scope_id_or_params is not None else "all"
        param_dict = params

    p_hash = _hash_params(param_dict)
    return f"analytics:{endpoint}:{s_level}:{s_id}:{p_hash}"


def make_prediction_cache_key(student_id: int, semester: int) -> str:
    """
    Constructs a cache key for student predictions.
    Format: prediction:student:{student_id}:sem:{semester}
    """
    return f"prediction:student:{student_id}:sem:{semester}"


def safe_cache_get(key: str, default: Any = None, version: Optional[int] = None) -> Any:
    """Fault-tolerant cache retrieval that falls back to default on Redis error."""
    try:
        return cache.get(key, default=default, version=version)
    except Exception as exc:
        logger.warning("Cache GET failed for key '%s': %s", key, exc)
        return default


def safe_cache_set(
    key: str,
    value: Any,
    timeout: int = DEFAULT_ANALYTICS_CACHE_TTL,
    version: Optional[int] = None,
) -> bool:
    """Fault-tolerant cache set that logs error and does not raise on Redis failure."""
    try:
        cache.set(key, value, timeout=timeout, version=version)
        return True
    except Exception as exc:
        logger.warning("Cache SET failed for key '%s': %s", key, exc)
        return False


def get_analytics_cache_version() -> int:
    """Retrieves current analytics generation version number."""
    try:
        v = cache.get(ANALYTICS_VERSION_KEY)
        if v is None:
            cache.set(ANALYTICS_VERSION_KEY, 1, timeout=None)
            return 1
        return int(v)
    except Exception as exc:
        logger.warning("Failed to get analytics cache version: %s", exc)
        return 1


def invalidate_analytics_cache() -> None:
    """
    Atomically increments the analytics cache generation version.
    Invalidates all cached analytics endpoints in O(1) time across Redis/LocMemCache.
    """
    try:
        try:
            cache.incr(ANALYTICS_VERSION_KEY)
        except Exception:
            curr = safe_cache_get(ANALYTICS_VERSION_KEY, default=1)
            cache.set(ANALYTICS_VERSION_KEY, int(curr) + 1, timeout=None)
        logger.info("Analytics cache invalidated (generation version incremented).")
    except Exception as exc:
        logger.warning("Failed to invalidate analytics cache: %s", exc)


def get_student_prediction_version(student_id: int) -> int:
    """Retrieves current prediction cache generation version for a specific student."""
    key = f"{STUDENT_VERSION_PREFIX}:{student_id}"
    try:
        v = cache.get(key)
        if v is None:
            cache.set(key, 1, timeout=None)
            return 1
        return int(v)
    except Exception as exc:
        logger.warning("Failed to get student prediction version for %s: %s", student_id, exc)
        return 1


def invalidate_student_prediction_cache(student_id: int) -> None:
    """
    Atomically increments prediction cache generation version for a student.
    Invalidates all cached predictions for that student in O(1) time.
    """
    key = f"{STUDENT_VERSION_PREFIX}:{student_id}"
    try:
        try:
            cache.incr(key)
        except Exception:
            curr = safe_cache_get(key, default=1)
            cache.set(key, int(curr) + 1, timeout=None)
        logger.info("Student prediction cache invalidated for student %s.", student_id)
    except Exception as exc:
        logger.warning("Failed to invalidate student prediction cache for %s: %s", student_id, exc)


def get_model_cache_version() -> int:
    """Retrieves current model registry cache version."""
    try:
        v = cache.get(MODEL_VERSION_KEY)
        if v is None:
            cache.set(MODEL_VERSION_KEY, 1, timeout=None)
            return 1
        return int(v)
    except Exception as exc:
        logger.warning("Failed to get model cache version: %s", exc)
        return 1


def invalidate_model_cache() -> None:
    """
    Invalidates both model registry and global prediction / analytics caches
    when a new model version is activated.
    """
    try:
        try:
            cache.incr(MODEL_VERSION_KEY)
        except Exception:
            curr = safe_cache_get(MODEL_VERSION_KEY, default=1)
            cache.set(MODEL_VERSION_KEY, int(curr) + 1, timeout=None)
        invalidate_analytics_cache()
        logger.info("Model cache and analytics cache invalidated.")
    except Exception as exc:
        logger.warning("Failed to invalidate model cache: %s", exc)
