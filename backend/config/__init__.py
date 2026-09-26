"""
EduPulse Django Configuration Package.
Exposes celery_app so shared_task decorators bind seamlessly.
"""

from .celery import celery_app

__all__ = ("celery_app",)
