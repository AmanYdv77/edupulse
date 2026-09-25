"""
DRF Serializers for the EduPulse Scoped Analytics API.
"""

from rest_framework import serializers


class ActiveModelInfoSerializer(serializers.Serializer):
    slot = serializers.CharField()
    version = serializers.IntegerField()
    algorithm = serializers.CharField()
    metrics = serializers.DictField()
    is_active = serializers.BooleanField()


class AnalyticsOverviewSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    pass_rate = serializers.FloatField()
    average_percentage = serializers.FloatField()
    at_risk_count = serializers.IntegerField()
    at_risk_rate = serializers.FloatField()
    published_share = serializers.FloatField()
    model = ActiveModelInfoSerializer(allow_null=True)


class AnalyticsBreakdownGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    code = serializers.CharField(allow_blank=True)
    student_count = serializers.IntegerField()
    pass_rate = serializers.FloatField()
    average_percentage = serializers.FloatField()


class AnalyticsBreakdownResponseSerializer(serializers.Serializer):
    by = serializers.CharField()
    groups = AnalyticsBreakdownGroupSerializer(many=True)


class AnalyticsTrendPointSerializer(serializers.Serializer):
    semester = serializers.IntegerField()
    value = serializers.FloatField()
    sample_size = serializers.IntegerField()


class AnalyticsTrendResponseSerializer(serializers.Serializer):
    metric = serializers.CharField()
    points = AnalyticsTrendPointSerializer(many=True)


class AnalyticsDistributionBinSerializer(serializers.Serializer):
    label = serializers.CharField()
    min = serializers.IntegerField()
    max = serializers.IntegerField()
    count = serializers.IntegerField()


class AnalyticsDistributionSubjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()


class AnalyticsDistributionResponseSerializer(serializers.Serializer):
    subject = AnalyticsDistributionSubjectSerializer()
    total_records = serializers.IntegerField()
    bins = AnalyticsDistributionBinSerializer(many=True)


class AtRiskStudentRosterSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    roll_no = serializers.CharField()
    name = serializers.CharField()
    batch_code = serializers.CharField()
    course_code = serializers.CharField()
    subject_code = serializers.CharField(allow_blank=True)
    semester = serializers.IntegerField()
    predicted_percentage = serializers.FloatField(allow_null=True)
    risk_band = serializers.CharField()
    reasons = serializers.ListField(child=serializers.CharField())
    taken_at = serializers.DateTimeField()
