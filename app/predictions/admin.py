from django.contrib import admin
from .models import ModelVersion


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "slot",
        "version",
        "is_active",
        "trained_on",
        "n_train_rows",
        "n_test_rows",
        "sklearn_version",
        "created_at",
    )
    list_filter = ("slot", "is_active", "sklearn_version")
    search_fields = ("trained_on", "artifact_file", "data_fingerprint")
    readonly_fields = ("created_at",)
