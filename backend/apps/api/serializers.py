"""
DRF Serializers for EduPulse Core REST API.
Enforces contract boundary ranges, data privacy, and uniform serialization shapes.
"""

from rest_framework import serializers
from accounts.models import User
from accounts.permissions import capabilities_for, scope_for
from academics.models import (
    StudentProfile,
    Result,
    SemesterResult,
    HabitCheckInLog,
    TeachingAssignment,
    Subject,
    Batch,
)
from predictions.models import ModelVersion


# ============================================================================
# Auth & Identity Serializers
# ============================================================================

class CSRFResponseSerializer(serializers.Serializer):
    csrfToken = serializers.CharField(help_text="CSRF token for unsafe state-mutating requests")


class LogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Logout status message")


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UserMeSerializer(serializers.Serializer):
    """
    Public representation of the authenticated user's session.
    Strictly excludes email, phone number, and protected demographics.
    """
    id = serializers.IntegerField(read_only=True)
    display_name = serializers.SerializerMethodField()
    role = serializers.CharField(read_only=True)
    scope_label = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    def get_display_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.username

    def get_scope_label(self, obj: User) -> str:
        scope = scope_for(obj)
        return scope.get("scope_label", "")

    def get_capabilities(self, obj: User) -> list[str]:
        return capabilities_for(obj)


# ============================================================================
# Academic Results Serializers
# ============================================================================

class SubjectResultItemSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.title", read_only=True)
    subject_credits = serializers.IntegerField(source="subject.credits", read_only=True)
    grade = serializers.CharField(source="letter_grade", read_only=True)

    class Meta:
        model = Result
        fields = [
            "id",
            "subject_code",
            "subject_name",
            "subject_credits",
            "semester",
            "internal_marks",
            "total_secured",
            "max_marks",
            "grade",
        ]


class SemesterResultItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemesterResult
        fields = [
            "id",
            "semester",
            "sgpa",
            "percentage",
            "attendance_percentage",
            "total_credits",
            "is_published",
        ]


class StudentResultsSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    roll_number = serializers.CharField()
    semester_results = SemesterResultItemSerializer(many=True)
    subject_results = SubjectResultItemSerializer(many=True)


# ============================================================================
# Predictions Serializers
# ============================================================================

class FactorDetailSerializer(serializers.Serializer):
    feature = serializers.CharField()
    name = serializers.CharField()
    impact = serializers.CharField()
    direction = serializers.CharField()
    description = serializers.CharField(required=False, default="")


class SubjectPredictionSerializer(serializers.Serializer):
    subject_code = serializers.CharField()
    subject_name = serializers.CharField()
    semester = serializers.IntegerField()
    predicted_score = serializers.FloatField(allow_null=True)
    confidence_score = serializers.FloatField(allow_null=True)
    risk_band = serializers.CharField(allow_null=True)
    model_label = serializers.CharField()
    model_version = serializers.IntegerField(allow_null=True)
    factors = FactorDetailSerializer(many=True)
    disclaimer = serializers.CharField()
    insufficient_data = serializers.BooleanField()
    insufficient_data_reasons = serializers.ListField(child=serializers.CharField())


class StudentPredictionsResponseSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    target_semester = serializers.IntegerField()
    predictions = SubjectPredictionSerializer(many=True)


# ============================================================================
class NormalizedChoiceField(serializers.ChoiceField):
    """Normalizes input strings to title case before validating against choices."""
    def to_internal_value(self, data):
        if data and isinstance(data, str):
            data = data.capitalize()
        return super().to_internal_value(data)


class HabitCheckInLogSerializer(serializers.ModelSerializer):
    motivation_level = NormalizedChoiceField(
        choices=HabitCheckInLog.MOTIVATION_CHOICES,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = HabitCheckInLog
        fields = [
            "id",
            "log_date",
            "log_type",
            "hours_studied",
            "sleep_hours",
            "motivation_level",
            "tutoring_sessions",
            "physical_activity",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_sleep_hours(self, value):
        if value is not None and not (0.0 <= float(value) <= 24.0):
            raise serializers.ValidationError("Sleep hours must be between 0.0 and 24.0.")
        return value

    def validate_motivation_level(self, value):
        if value:
            cap = str(value).capitalize()
            if cap in ("Low", "Medium", "High"):
                return cap
        return value

    def validate(self, attrs):
        log_type = attrs.get("log_type", getattr(self.instance, "log_type", "DAILY"))
        hours_studied = attrs.get("hours_studied")

        if hours_studied is not None:
            hours_val = float(hours_studied)
            if log_type == "DAILY" and not (0.0 <= hours_val <= 24.0):
                raise serializers.ValidationError(
                    {"hours_studied": "Daily study hours must be between 0.0 and 24.0."}
                )
            if log_type == "WEEKLY" and not (0.0 <= hours_val <= 168.0):
                raise serializers.ValidationError(
                    {"hours_studied": "Weekly study hours must be between 0.0 and 168.0."}
                )

        tutoring = attrs.get("tutoring_sessions")
        if tutoring is not None and tutoring < 0:
            raise serializers.ValidationError(
                {"tutoring_sessions": "Tutoring sessions cannot be negative."}
            )

        physical = attrs.get("physical_activity")
        if physical is not None and float(physical) < 0:
            raise serializers.ValidationError(
                {"physical_activity": "Physical activity cannot be negative."}
            )

        return attrs


# ============================================================================
# Faculty & Internal Marks Serializers
# ============================================================================

class TeachingAssignmentSerializer(serializers.ModelSerializer):
    subject_id = serializers.IntegerField(source="subject.id", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.title", read_only=True)
    internal_max = serializers.IntegerField(source="subject.internal_max", read_only=True)
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)
    batch_name = serializers.CharField(source="batch.batch_code", read_only=True)
    course_name = serializers.CharField(source="batch.course.name", read_only=True)
    semester = serializers.IntegerField(source="subject.semester", read_only=True)

    class Meta:
        model = TeachingAssignment
        fields = [
            "id",
            "subject_id",
            "subject_code",
            "subject_name",
            "internal_max",
            "batch_id",
            "batch_name",
            "course_name",
            "semester",
        ]


class SingleMarkEntrySerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    internal_marks = serializers.DecimalField(max_digits=5, decimal_places=2)


class BulkInternalMarksRequestSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    batch_id = serializers.IntegerField()
    marks = SingleMarkEntrySerializer(many=True)


class BulkInternalMarksResponseSerializer(serializers.Serializer):
    updated_count = serializers.IntegerField()
    detail = serializers.CharField()


# ============================================================================
# Model Registry Serializers
# ============================================================================

class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = [
            "id",
            "slot",
            "version",
            "is_active",
            "created_at",
            "trained_on",
            "n_train_rows",
            "n_test_rows",
            "metrics",
            "feature_names",
            "artifact_file",
        ]
