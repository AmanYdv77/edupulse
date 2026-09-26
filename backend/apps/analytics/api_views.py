"""
DRF API Views for the EduPulse Scoped Analytics Family (/api/v1/analytics/).
Provides scoped overview, breakdown with differential privacy, longitudinal trends,
score distributions, paginated at-risk rosters, and audited CSV exports.
"""

import csv
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.caching import (
    get_analytics_cache_version,
    make_analytics_cache_key,
    safe_cache_get,
    safe_cache_set,
)
from api.pagination import StandardResultsSetPagination
from api.permissions import CanExportAtRiskRoster, CanViewAnalytics, CanViewAtRiskRoster
from api.throttling import ExportRateThrottle, UserReadRateThrottle

from .models import ExportAuditLog
from .selectors import (
    get_analytics_breakdown,
    get_analytics_distribution,
    get_analytics_overview,
    get_analytics_trend,
    get_at_risk_snapshots_queryset,
    get_scope_context,
)
from .serializers import (
    AnalyticsBreakdownResponseSerializer,
    AnalyticsDistributionResponseSerializer,
    AnalyticsOverviewSerializer,
    AnalyticsTrendResponseSerializer,
    AtRiskStudentRosterSerializer,
)


def _serialize_snapshot(snap) -> dict:
    """Helper formatting PredictionSnapshot into flat dictionary for serializer."""
    return {
        "student_id": snap.student_id,
        "roll_no": snap.student.roll_no,
        "name": snap.student.user.get_full_name() or snap.student.user.username,
        "batch_code": snap.student.batch.batch_code if snap.student.batch else "",
        "course_code": snap.student.course.code if snap.student.course else "",
        "subject_code": snap.subject.code if snap.subject else "",
        "semester": snap.semester,
        "predicted_percentage": round(snap.predicted_percentage, 1)
        if snap.predicted_percentage is not None
        else None,
        "risk_band": snap.risk_band,
        "reasons": snap.reasons if isinstance(snap.reasons, list) else [],
        "taken_at": snap.taken_at,
    }


class AnalyticsOverviewAPIView(APIView):
    """
    Returns top-level KPI overview (total students, pass rate, avg score, at-risk count/rate, published share, model).
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAnalytics]
    throttle_classes = [UserReadRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Get institutional analytics overview KPIs",
        description="Returns top-level KPIs scoped to caller's academic role. Database-aggregated, zero student-by-student loops.",
        parameters=[
            OpenApiParameter("school", int, description="School ID filter"),
            OpenApiParameter("department", int, description="Department ID filter"),
            OpenApiParameter("course", int, description="Course ID filter"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
            OpenApiParameter("semester", int, description="Semester number filter"),
        ],
        responses={200: AnalyticsOverviewSerializer},
    )
    def get(self, request):
        scope_ctx = get_scope_context(request.user)
        cache_key = make_analytics_cache_key(
            "overview",
            scope_ctx,
            request.query_params.dict(),
        )
        version = get_analytics_cache_version()
        cached = safe_cache_get(cache_key, version=version)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        data = get_analytics_overview(scope_ctx, request.query_params)
        serializer = AnalyticsOverviewSerializer(data)
        safe_cache_set(cache_key, serializer.data, version=version)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AnalyticsBreakdownAPIView(APIView):
    """
    Returns performance breakdown strictly by levels below user's scope.
    Groups smaller than ANALYTICS_MIN_GROUP_SIZE are merged into 'Other (hidden)'.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAnalytics]
    throttle_classes = [UserReadRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Get scoped performance breakdown",
        description="Aggregates performance by level strictly below user's academic scope with differential privacy (groups < 10 merged into 'Other (hidden)').",
        parameters=[
            OpenApiParameter(
                "by",
                str,
                required=True,
                description="Breakdown level (school, department, course, batch, subject, teacher)",
            ),
            OpenApiParameter("school", int, description="School ID filter"),
            OpenApiParameter("department", int, description="Department ID filter"),
            OpenApiParameter("course", int, description="Course ID filter"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
            OpenApiParameter("semester", int, description="Semester number filter"),
        ],
        responses={200: AnalyticsBreakdownResponseSerializer},
    )
    def get(self, request):
        by = request.query_params.get("by")
        if not by:
            raise ParseError("The 'by' query parameter is required.")
        if by not in ("school", "department", "course", "batch", "subject", "teacher"):
            raise ParseError(
                "The 'by' parameter must be one of: school, department, course, batch, subject, teacher."
            )

        scope_ctx = get_scope_context(request.user)
        cache_key = make_analytics_cache_key(
            f"breakdown_{by}",
            scope_ctx,
            request.query_params.dict(),
        )
        version = get_analytics_cache_version()
        cached = safe_cache_get(cache_key, version=version)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        data = get_analytics_breakdown(scope_ctx, by, request.query_params)
        serializer = AnalyticsBreakdownResponseSerializer(data)
        safe_cache_set(cache_key, serializer.data, version=version)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AnalyticsTrendAPIView(APIView):
    """
    Returns longitudinal performance trend per semester across academic history.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAnalytics]
    throttle_classes = [UserReadRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Get longitudinal performance trend",
        description="Returns metrics per semester across academic history.",
        parameters=[
            OpenApiParameter(
                "metric",
                str,
                required=True,
                description="Metric: pass_rate, avg_percentage, at_risk_rate",
            ),
            OpenApiParameter("school", int, description="School ID filter"),
            OpenApiParameter("department", int, description="Department ID filter"),
            OpenApiParameter("course", int, description="Course ID filter"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
        ],
        responses={200: AnalyticsTrendResponseSerializer},
    )
    def get(self, request):
        metric = request.query_params.get("metric")
        if not metric:
            raise ParseError("The 'metric' query parameter is required.")
        if metric not in ("pass_rate", "avg_percentage", "at_risk_rate"):
            raise ParseError(
                "The 'metric' parameter must be one of: pass_rate, avg_percentage, at_risk_rate."
            )

        scope_ctx = get_scope_context(request.user)
        cache_key = make_analytics_cache_key(
            f"trend_{metric}",
            scope_ctx,
            request.query_params.dict(),
        )
        version = get_analytics_cache_version()
        cached = safe_cache_get(cache_key, version=version)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        data = get_analytics_trend(scope_ctx, metric, request.query_params)
        serializer = AnalyticsTrendResponseSerializer(data)
        safe_cache_set(cache_key, serializer.data, version=version)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AnalyticsDistributionAPIView(APIView):
    """
    Returns fixed-bin percentage score histogram for a subject within user's scope.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAnalytics]
    throttle_classes = [UserReadRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Get score histogram distribution for a subject",
        description="Computes fixed-bin percentage score histogram for a subject within user's scope.",
        parameters=[
            OpenApiParameter("subject", int, required=True, description="Subject ID"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
            OpenApiParameter("semester", int, description="Semester number filter"),
        ],
        responses={200: AnalyticsDistributionResponseSerializer},
    )
    def get(self, request):
        subject_id_raw = request.query_params.get("subject")
        if not subject_id_raw:
            raise ParseError("The 'subject' query parameter is required.")
        try:
            subject_id = int(subject_id_raw)
        except ValueError:
            raise ParseError("The 'subject' query parameter must be a valid integer ID.")

        scope_ctx = get_scope_context(request.user)
        cache_key = make_analytics_cache_key(
            f"distribution_{subject_id}",
            scope_ctx,
            request.query_params.dict(),
        )
        version = get_analytics_cache_version()
        cached = safe_cache_get(cache_key, version=version)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        data = get_analytics_distribution(scope_ctx, subject_id, request.query_params)
        serializer = AnalyticsDistributionResponseSerializer(data)
        safe_cache_set(cache_key, serializer.data, version=version)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AtRiskRosterAPIView(APIView):
    """
    Returns paginated at-risk student records from latest prediction snapshots.
    Requires view_at_risk_roster capability (Faculty only: HOD, Dean).
    Executives, Teachers, and Students receive HTTP 403 Forbidden.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAtRiskRoster]
    throttle_classes = [UserReadRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Get paginated roster of at-risk students",
        description="Returns paginated at-risk student records from latest prediction snapshots. Requires view_at_risk_roster capability (Faculty only; Executives receive 403).",
        parameters=[
            OpenApiParameter("course", int, description="Course ID filter"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
            OpenApiParameter("semester", int, description="Semester number filter"),
            OpenApiParameter("page", int, description="Page number"),
        ],
        responses={200: AtRiskStudentRosterSerializer(many=True)},
    )
    def get(self, request):
        scope_ctx = get_scope_context(request.user)
        qs = get_at_risk_snapshots_queryset(scope_ctx, request.query_params)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            data = [_serialize_snapshot(snap) for snap in page]
            serializer = AtRiskStudentRosterSerializer(data, many=True)
            return paginator.get_paginated_response(serializer.data)

        data = [_serialize_snapshot(snap) for snap in qs]
        serializer = AtRiskStudentRosterSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AtRiskExportCSVAPIView(APIView):
    """
    Downloads CSV export of at-risk students.
    Throttled to 5 exports/hour per user.
    Creates an immutable ExportAuditLog record.
    """

    permission_classes = [permissions.IsAuthenticated, CanExportAtRiskRoster]
    throttle_classes = [ExportRateThrottle]

    @extend_schema(
        tags=["Analytics"],
        summary="Export at-risk student roster as CSV",
        description="Downloads CSV export of at-risk students. Throttled to 5 exports/hour per user. Creates an audit log record.",
        parameters=[
            OpenApiParameter("course", int, description="Course ID filter"),
            OpenApiParameter("batch", int, description="Batch ID filter"),
            OpenApiParameter("semester", int, description="Semester number filter"),
        ],
        responses={200: OpenApiResponse(description="CSV file download")},
    )
    def get(self, request):
        scope_ctx = get_scope_context(request.user)
        qs = get_at_risk_snapshots_queryset(scope_ctx, request.query_params)

        sanitized_filters = {}
        for param in ("course", "batch", "semester"):
            val = request.query_params.get(param)
            if val:
                sanitized_filters[param] = val

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="at_risk_roster.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Roll No",
                "Name",
                "Batch",
                "Course",
                "Subject",
                "Semester",
                "Risk Band",
                "Predicted Percentage",
                "Reasons",
                "Taken At",
            ]
        )

        row_count = 0
        for snap in qs:
            row_count += 1
            writer.writerow(
                [
                    snap.student.roll_no,
                    snap.student.user.get_full_name() or snap.student.user.username,
                    snap.student.batch.batch_code if snap.student.batch else "",
                    snap.student.course.code if snap.student.course else "",
                    snap.subject.code if snap.subject else "",
                    snap.semester,
                    snap.risk_band,
                    round(snap.predicted_percentage, 1)
                    if snap.predicted_percentage is not None
                    else "",
                    "; ".join(snap.reasons) if isinstance(snap.reasons, list) else str(snap.reasons),
                    snap.taken_at.isoformat() if snap.taken_at else "",
                ]
            )

        # Create immutable audit log entry
        ExportAuditLog.objects.create(
            user=request.user,
            scope_level=scope_ctx.scope_level,
            filters_applied=sanitized_filters,
            row_count=row_count,
        )

        return response
