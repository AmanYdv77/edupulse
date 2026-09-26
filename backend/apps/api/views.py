"""
DRF ViewSets and API Views for EduPulse Core REST API.
Enforces default-deny, role capabilities, scope isolation, and OpenAPI documentation.
"""

from decimal import Decimal
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import permissions, status, views
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from academics.models import (
    Batch,
    HabitCheckInLog,
    Result,
    SemesterResult,
    StudentProfile,
    StudentHabitPreference,
    Subject,
    TeachingAssignment,
)
from predictions.models import ModelVersion
from predictions.services import PredictorService, predict_for_students

from .caching import (
    get_student_prediction_version,
    make_prediction_cache_key,
    safe_cache_get,
    safe_cache_set,
)
from .pagination import StandardResultsSetPagination
from .permissions import (
    IsSelfOrInStaffScope,
    IsStudentUser,
    IsSystemAdminUser,
    IsTeacherUser,
    StaffOrDevOnly,
)
from .serializers import (
    BulkInternalMarksRequestSerializer,
    BulkInternalMarksResponseSerializer,
    CSRFResponseSerializer,
    LogoutResponseSerializer,
    HabitCheckInLogSerializer,
    LoginRequestSerializer,
    ModelVersionSerializer,
    StudentPredictionsResponseSerializer,
    StudentResultsSerializer,
    TeachingAssignmentSerializer,
    UserMeSerializer,
)
from .throttling import LoginRateThrottle


# ============================================================================
# 1. CSRF & Authentication Views
# ============================================================================

class CSRFView(views.APIView):
    """
    Returns a fresh CSRF token required for state-mutating requests (POST, PUT, DELETE).
    Publicly accessible.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Retrieve CSRF Token",
        description="Returns a valid CSRF token to be included in the X-CSRFToken header for unsafe requests.",
        responses={200: CSRFResponseSerializer},
        tags=["Authentication"],
    )
    def get(self, request):
        token = get_token(request)
        return Response({"csrfToken": token})


class LoginView(views.APIView):
    """
    Session-cookie login endpoint.
    Throttled to 5 requests/minute per IP and username.
    Employs generic error messaging on authentication failure to prevent credential enumeration.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        summary="Session Login",
        description="Authenticates the user and initiates an HTTP-only session cookie.",
        request=LoginRequestSerializer,
        responses={
            200: UserMeSerializer,
            400: OpenApiResponse(description="Invalid username or password / inactive account"),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "validation_error",
                    "detail": "Username and password are required.",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {
                    "code": "authentication_failed",
                    "detail": "Invalid username or password.",
                    "fields": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {
                    "code": "authentication_failed",
                    "detail": "Account is inactive. Please contact your system administrator.",
                    "fields": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        return Response(UserMeSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(views.APIView):
    """
    Terminates the active session and invalidates the session cookie.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Session Logout",
        description="Terminates the current user session.",
        request=None,
        responses={200: LogoutResponseSerializer},
        tags=["Authentication"],
    )
    def post(self, request):
        logout(request)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


# ============================================================================
# 2. Identity & Capability View
# ============================================================================

class UserMeView(views.APIView):
    """
    Returns the authenticated user's profile, role, scope label, and capability list.
    Excludes email, phone numbers, and demographic attributes.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Current User Context",
        description="Returns active session details, server-derived scope, and granular UI capabilities.",
        responses={200: UserMeSerializer},
        tags=["Identity"],
    )
    def get(self, request):
        return Response(UserMeSerializer(request.user).data)


# ============================================================================
# 3. Student Academic Results & Predictions Views
# ============================================================================

class StudentResultsView(views.APIView):
    """
    Returns academic history (semester results and subject results) for a student.
    Enforces strict scope isolation:
    - Students may only view their own results.
    - Faculty may only view students within their taught batch / department / school.
    - Executives (VC, Registrar, Controller) receive 403 (aggregates only).
    """
    permission_classes = [permissions.IsAuthenticated, IsSelfOrInStaffScope]

    @extend_schema(
        summary="Student Academic Results",
        description="Retrieves official semester and subject results for the specified student ID.",
        parameters=[
            OpenApiParameter("id", int, OpenApiParameter.PATH, description="Student ID"),
        ],
        responses={
            200: StudentResultsSerializer,
            403: OpenApiResponse(description="Access denied: outside user scope"),
            404: OpenApiResponse(description="Student not found"),
        },
        tags=["Academics"],
    )
    def get(self, request, id: int):
        student = get_object_or_404(StudentProfile, pk=id)
        self.check_object_permissions(request, student)

        # Query semester results
        sem_qs = SemesterResult.objects.filter(student=student).order_by("semester")
        # Students only see published semester results
        if getattr(request.user, "role", None) == "STUDENT":
            sem_qs = sem_qs.filter(is_published=True)

        # Query subject results
        subj_qs = Result.objects.filter(student=student).select_related("subject").order_by("semester", "subject__code")

        data = {
            "student_id": student.id,
            "roll_number": student.roll_no,
            "semester_results": list(sem_qs),
            "subject_results": list(subj_qs),
        }
        return Response(StudentResultsSerializer(data).data)


class StudentPredictionsView(views.APIView):
    """
    Returns real-time grade forecasts for a student generated by PredictorService.
    Includes honest model labels, top explanatory factors, disclaimer, and insufficient data reasons.
    Enforces the same scope isolation as results.
    """
    permission_classes = [permissions.IsAuthenticated, IsSelfOrInStaffScope]

    @extend_schema(
        summary="Student Performance Predictions",
        description="Generates real-time score forecasts and advisory explanations for the specified student ID.",
        parameters=[
            OpenApiParameter("id", int, OpenApiParameter.PATH, description="Student ID"),
            OpenApiParameter("semester", int, OpenApiParameter.QUERY, description="Target semester (defaults to current)", required=False),
        ],
        responses={
            200: StudentPredictionsResponseSerializer,
            403: OpenApiResponse(description="Access denied: outside user scope"),
            404: OpenApiResponse(description="Student not found"),
        },
        tags=["Predictions"],
    )
    def get(self, request, id: int):
        student = get_object_or_404(StudentProfile, pk=id)
        self.check_object_permissions(request, student)

        target_sem = request.query_params.get("semester")
        if target_sem:
            try:
                target_sem = int(target_sem)
            except ValueError:
                target_sem = student.current_semester
        else:
            target_sem = student.current_semester

        cache_key = make_prediction_cache_key(student.id, target_sem)
        version = get_student_prediction_version(student.id)
        cached = safe_cache_get(cache_key, version=version)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        active_models = PredictorService.get_active_models()
        mv = PredictorService.active_for(student, active_models=active_models) if active_models else None
        if not mv and active_models:
            mv = active_models.get("baseline") or active_models.get("institute")

        predictions = (
            predict_for_students([student], model_version=mv, semester=target_sem)
            if mv
            else []
        )

        prediction_items = []
        for p in predictions:
            prediction_items.append({
                "subject_code": p.subject_code,
                "subject_name": p.subject_title,
                "semester": p.semester,
                "predicted_score": round(p.predicted_percentage, 1) if p.predicted_percentage is not None else None,
                "confidence_score": 0.85 if p.predicted_percentage is not None else None,
                "risk_band": p.risk_band,
                "model_label": p.model_label,
                "model_version": p.model_version,
                "factors": p.factors,
                "disclaimer": p.disclaimer,
                "insufficient_data": p.predicted_percentage is None,
                "insufficient_data_reasons": p.reasons,
            })

        data = {
            "student_id": student.id,
            "target_semester": target_sem,
            "predictions": prediction_items,
        }
        serialized = StudentPredictionsResponseSerializer(data).data
        safe_cache_set(cache_key, serialized, timeout=600, version=version)
        return Response(serialized, status=status.HTTP_200_OK)


# ============================================================================
# 4. Habits Check-In Views
# ============================================================================

class HabitCheckInListCreateView(views.APIView):
    """
    Dedicated endpoint for students to log habits and view their check-in history.
    Restricted to authenticated students.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentUser]
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        summary="List Habit Check-Ins",
        description="Returns paginated history of habit check-ins for the currently authenticated student.",
        responses={200: HabitCheckInLogSerializer(many=True)},
        tags=["Habits"],
    )
    def get(self, request):
        student = request.user.student_profile
        logs_qs = HabitCheckInLog.objects.filter(student=student).order_by("-log_date", "-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(logs_qs, request, view=self)
        if page is not None:
            serializer = HabitCheckInLogSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = HabitCheckInLogSerializer(logs_qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Record Habit Check-In",
        description="Submits a daily or weekly habit check-in, validated against contract boundary ranges.",
        request=HabitCheckInLogSerializer,
        responses={
            201: HabitCheckInLogSerializer,
            400: OpenApiResponse(description="Input range validation failed"),
        },
        tags=["Habits"],
    )
    def post(self, request):
        student = request.user.student_profile
        serializer = HabitCheckInLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "validation_error",
                    "detail": "Habit check-in validation failed.",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        log_date = serializer.validated_data.get("log_date", today)

        with transaction.atomic():
            log = serializer.save(student=student, log_date=log_date)

            # Update habit streak if preference exists
            habit_pref, _ = StudentHabitPreference.objects.get_or_create(student=student)
            from datetime import timedelta
            if habit_pref.last_checkin_date:
                if habit_pref.last_checkin_date == today - timedelta(days=1):
                    habit_pref.streak_count += 1
                elif habit_pref.last_checkin_date == today:
                    pass  # already checked in today
                else:
                    habit_pref.streak_count = 1
            else:
                habit_pref.streak_count = 1

            habit_pref.last_checkin_date = today
            habit_pref.save()

        return Response(HabitCheckInLogSerializer(log).data, status=status.HTTP_201_CREATED)


# ============================================================================
# 5. Faculty Teaching Assignments & Internal Marks Views
# ============================================================================

class TeachingAssignmentsView(views.APIView):
    """
    Returns active teaching assignments for the authenticated teacher.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherUser]

    @extend_schema(
        summary="Faculty Teaching Assignments",
        description="Lists all courses, batches, and subjects currently assigned to the authenticated teacher.",
        responses={200: TeachingAssignmentSerializer(many=True)},
        tags=["Faculty"],
    )
    def get(self, request):
        teacher = request.user.teacher_profile
        assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related(
            "subject", "batch", "batch__course"
        )
        return Response(TeachingAssignmentSerializer(assignments, many=True).data)


class BulkInternalMarksView(views.APIView):
    """
    Bulk, atomic entry of continuous internal assessment marks.
    Enforces that the submitting teacher is assigned to the specified subject and batch.
    Validates all marks (0 <= mark <= subject.internal_max).
    Returns per-row error reporting if any row fails validation.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherUser]

    @extend_schema(
        summary="Bulk Internal Marks Entry",
        description="Atomically updates internal marks for students in an assigned subject and batch.",
        request=BulkInternalMarksRequestSerializer,
        responses={
            200: BulkInternalMarksResponseSerializer,
            400: OpenApiResponse(description="Per-row validation error report"),
            403: OpenApiResponse(description="Teacher is not assigned to this subject and batch"),
        },
        tags=["Faculty"],
    )
    def post(self, request):
        serializer = BulkInternalMarksRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "validation_error",
                    "detail": "Invalid internal marks payload structure.",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        teacher = request.user.teacher_profile
        subject_id = serializer.validated_data["subject_id"]
        batch_id = serializer.validated_data["batch_id"]
        marks_entries = serializer.validated_data["marks"]

        # 1. Assignment Authorization Check
        is_assigned = TeachingAssignment.objects.filter(
            teacher=teacher,
            subject_id=subject_id,
            batch_id=batch_id,
        ).exists()

        if not is_assigned:
            raise PermissionDenied("You are not assigned to teach this subject and batch.")

        subject = get_object_or_404(Subject, pk=subject_id)
        batch = get_object_or_404(Batch, pk=batch_id)
        internal_max = Decimal(str(subject.internal_max or 25))

        # 2. Pre-validate every single mark entry
        row_errors = []
        batch_student_ids = set(batch.students.values_list("id", flat=True))

        for idx, entry in enumerate(marks_entries, start=1):
            student_id = entry["student_id"]
            mark_val = Decimal(str(entry["internal_marks"]))

            if student_id not in batch_student_ids:
                row_errors.append({
                    "row": idx,
                    "student_id": student_id,
                    "error": f"Student ID {student_id} is not enrolled in batch '{batch.name}'.",
                })
                continue

            if mark_val < Decimal("0.0"):
                row_errors.append({
                    "row": idx,
                    "student_id": student_id,
                    "error": "Internal marks cannot be negative.",
                })
            elif mark_val > internal_max:
                row_errors.append({
                    "row": idx,
                    "student_id": student_id,
                    "error": f"Internal marks ({mark_val}) exceed subject maximum ({internal_max}).",
                })

        if row_errors:
            return Response(
                {
                    "code": "validation_error",
                    "detail": "One or more mark entries failed validation.",
                    "fields": {"marks": row_errors},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Atomic Database Update
        with transaction.atomic():
            for entry in marks_entries:
                student_id = entry["student_id"]
                mark_val = entry["internal_marks"]

                result, _ = Result.objects.get_or_create(
                    student_id=student_id,
                    subject=subject,
                    defaults={
                        "semester": subject.semester,
                        "max_marks": 100,
                        "total_secured": 0,
                    },
                )
                result.internal_marks = int(round(float(mark_val)))
                result.save(update_fields=["internal_marks"])

        return Response(
            {
                "updated_count": len(marks_entries),
                "detail": f"Successfully updated internal marks for {len(marks_entries)} student(s).",
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# 6. Model Registry Views
# ============================================================================

class ModelVersionListView(views.APIView):
    """
    Returns registered machine learning models and candidate benchmarks.
    Restricted to SYSTEM_ADMIN role only.
    """
    permission_classes = [permissions.IsAuthenticated, IsSystemAdminUser]

    @extend_schema(
        summary="List Model Registry Versions",
        description="Inspects registered baseline and institutional models, evaluation metrics, and active states.",
        responses={200: ModelVersionSerializer(many=True)},
        tags=["Admin"],
    )
    def get(self, request):
        models = ModelVersion.objects.all().order_by("-id")
        return Response(ModelVersionSerializer(models, many=True).data)
