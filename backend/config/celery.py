"""
Celery background worker and scheduler configuration for EduPulse.
"""

import os
from celery import Celery

# Default to dev settings if not explicitly provided
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("edupulse")

# Read Celery configuration from Django settings using the 'CELERY_' prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover task modules across all installed Django apps
app.autodiscover_tasks()

celery_app = app
