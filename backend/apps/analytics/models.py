"""
Database models for the analytics domain.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ExportAuditLog(models.Model):
    """
    Immutable audit log for scoped analytics data exports (e.g. at-risk student rosters).
    Maintains accountability and compliance without storing exported student PII in the log.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_export_logs",
        help_text="User who initiated the export.",
    )
    scope_level = models.CharField(
        max_length=50,
        help_text="Academic scope level of the user at export time (e.g. 'teacher', 'department', 'school').",
    )
    filters_applied = models.JSONField(
        default=dict,
        help_text="Filter parameters applied during the export.",
    )
    row_count = models.PositiveIntegerField(
        help_text="Total number of student records exported.",
    )
    exported_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp when the export occurred.",
    )

    class Meta:
        ordering = ["-exported_at", "-id"]
        verbose_name = "Export Audit Log"
        verbose_name_plural = "Export Audit Logs"

    def __str__(self):
        return f"Export by User {self.user_id} ({self.scope_level}) - {self.row_count} rows at {self.exported_at}"
