"""
Database selectors and scope-bounded aggregation engines for EduPulse Analytics.
Enforces 100% database ORM aggregation, zero student-by-student Python loops,
differential privacy thresholds (ANALYTICS_MIN_GROUP_SIZE = 10), and strict academic scope isolation.
"""

from dataclasses import dataclass
from typing import Any, Optional
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import (
    Avg,
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)

from academics.models import (
    Batch,
    Course,
    Department,
    Result,
    School,
    SemesterResult,
    StudentProfile,
    Subject,
    TeachingAssignment,
)
from predictions.models import ModelVersion, PredictionSnapshot


@dataclass(frozen=True)
class ScopeContext:
    user: Any
    role: str
    scope_level: str  # "university", "school", "department", "teacher", "none"
    is_university_wide: bool
    allowed_school_ids: set[int]
    allowed_department_ids: set[int]
    allowed_course_ids: set[int]
    allowed_batch_ids: set[int]
    allowed_subject_ids: set[int]


def get_scope_context(user) -> ScopeContext:
    """
    Derives the complete academic ScopeContext for the given user.
    """
    if not user or not user.is_authenticated or not getattr(user, "is_active", False):
        return ScopeContext(
            user=user,
            role="ANONYMOUS",
            scope_level="none",
            is_university_wide=False,
            allowed_school_ids=set(),
            allowed_department_ids=set(),
            allowed_course_ids=set(),
            allowed_batch_ids=set(),
            allowed_subject_ids=set(),
        )

    role = getattr(user, "role", None)

    # 1. Executive Roles (University-Wide)
    if role in ("VC", "REGISTRAR", "CONTROLLER_OF_EXAMS"):
        return ScopeContext(
            user=user,
            role=role,
            scope_level="university",
            is_university_wide=True,
            allowed_school_ids=set(),
            allowed_department_ids=set(),
            allowed_course_ids=set(),
            allowed_batch_ids=set(),
            allowed_subject_ids=set(),
        )

    # 2. Dean (School Scope)
    if role == "DEAN":
        school = getattr(user, "school", None)
        if school:
            school_ids = {school.id}
            dept_ids = set(Department.objects.filter(school=school).values_list("id", flat=True))
            course_ids = set(Course.objects.filter(department_id__in=dept_ids).values_list("id", flat=True))
            batch_ids = set(Batch.objects.filter(course_id__in=course_ids).values_list("id", flat=True))
            subject_ids = set(Subject.objects.filter(course_id__in=course_ids).values_list("id", flat=True))
        else:
            school_ids = set()
            dept_ids = set()
            course_ids = set()
            batch_ids = set()
            subject_ids = set()

        return ScopeContext(
            user=user,
            role=role,
            scope_level="school",
            is_university_wide=False,
            allowed_school_ids=school_ids,
            allowed_department_ids=dept_ids,
            allowed_course_ids=course_ids,
            allowed_batch_ids=batch_ids,
            allowed_subject_ids=subject_ids,
        )

    # 3. HOD (Department Scope)
    if role == "HOD":
        dept = getattr(user, "department", None)
        if not dept and hasattr(user, "teacher_profile"):
            dept = getattr(user.teacher_profile, "department", None)

        if dept:
            dept_ids = {dept.id}
            school_ids = {dept.school_id} if dept.school_id else set()
            course_ids = set(Course.objects.filter(department=dept).values_list("id", flat=True))
            batch_ids = set(Batch.objects.filter(course_id__in=course_ids).values_list("id", flat=True))
            subject_ids = set(Subject.objects.filter(course_id__in=course_ids).values_list("id", flat=True))
        else:
            dept_ids = set()
            school_ids = set()
            course_ids = set()
            batch_ids = set()
            subject_ids = set()

        return ScopeContext(
            user=user,
            role=role,
            scope_level="department",
            is_university_wide=False,
            allowed_school_ids=school_ids,
            allowed_department_ids=dept_ids,
            allowed_course_ids=course_ids,
            allowed_batch_ids=batch_ids,
            allowed_subject_ids=subject_ids,
        )

    # 4. Teacher (Assigned Batches and Subjects)
    if role == "TEACHER":
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            assignments = TeachingAssignment.objects.filter(teacher=teacher)
            batch_ids = set(assignments.values_list("batch_id", flat=True))
            subject_ids = set(assignments.values_list("subject_id", flat=True))
            course_ids = set(Batch.objects.filter(id__in=batch_ids).values_list("course_id", flat=True))
            dept_ids = set(Course.objects.filter(id__in=course_ids).values_list("department_id", flat=True))
            school_ids = set(Department.objects.filter(id__in=dept_ids).values_list("school_id", flat=True))
        else:
            batch_ids = set()
            subject_ids = set()
            course_ids = set()
            dept_ids = set()
            school_ids = set()

        return ScopeContext(
            user=user,
            role=role,
            scope_level="teacher",
            is_university_wide=False,
            allowed_school_ids=school_ids,
            allowed_department_ids=dept_ids,
            allowed_course_ids=course_ids,
            allowed_batch_ids=batch_ids,
            allowed_subject_ids=subject_ids,
        )

    # 5. Students, System Admins, or others without academic analytics scope
    return ScopeContext(
        user=user,
        role=role or "UNKNOWN",
        scope_level="none",
        is_university_wide=False,
        allowed_school_ids=set(),
        allowed_department_ids=set(),
        allowed_course_ids=set(),
        allowed_batch_ids=set(),
        allowed_subject_ids=set(),
    )


def validate_and_filter_students(scope_ctx: ScopeContext, filters: dict) -> tuple[Any, dict]:
    """
    Validates client-supplied filters against the user's ScopeContext.
    Raises PermissionDenied (HTTP 403) if any requested entity is outside caller's authorized scope.
    Returns (filtered_student_queryset, sanitized_filters_dict).
    """
    if scope_ctx.scope_level == "none":
        raise PermissionDenied("You do not have permission to access analytics.")

    sanitized = {}

    school_id = filters.get("school")
    department_id = filters.get("department")
    course_id = filters.get("course")
    batch_id = filters.get("batch")
    semester = filters.get("semester")

    # 1. Validate Entity IDs against ScopeContext
    if school_id is not None:
        try:
            school_id = int(school_id)
        except (ValueError, TypeError):
            raise PermissionDenied("Invalid school filter.")
        if not scope_ctx.is_university_wide and school_id not in scope_ctx.allowed_school_ids:
            raise PermissionDenied("Requested school is outside your authorized academic scope.")
        elif scope_ctx.is_university_wide and not School.objects.filter(id=school_id).exists():
            raise PermissionDenied("Requested school does not exist.")
        sanitized["school"] = school_id

    if department_id is not None:
        try:
            department_id = int(department_id)
        except (ValueError, TypeError):
            raise PermissionDenied("Invalid department filter.")
        if not scope_ctx.is_university_wide and department_id not in scope_ctx.allowed_department_ids:
            raise PermissionDenied("Requested department is outside your authorized academic scope.")
        elif scope_ctx.is_university_wide and not Department.objects.filter(id=department_id).exists():
            raise PermissionDenied("Requested department does not exist.")
        sanitized["department"] = department_id

    if course_id is not None:
        try:
            course_id = int(course_id)
        except (ValueError, TypeError):
            raise PermissionDenied("Invalid course filter.")
        if not scope_ctx.is_university_wide and course_id not in scope_ctx.allowed_course_ids:
            raise PermissionDenied("Requested course is outside your authorized academic scope.")
        elif scope_ctx.is_university_wide and not Course.objects.filter(id=course_id).exists():
            raise PermissionDenied("Requested course does not exist.")
        sanitized["course"] = course_id

    if batch_id is not None:
        try:
            batch_id = int(batch_id)
        except (ValueError, TypeError):
            raise PermissionDenied("Invalid batch filter.")
        if not scope_ctx.is_university_wide and batch_id not in scope_ctx.allowed_batch_ids:
            raise PermissionDenied("Requested batch is outside your authorized academic scope.")
        elif scope_ctx.is_university_wide and not Batch.objects.filter(id=batch_id).exists():
            raise PermissionDenied("Requested batch does not exist.")
        sanitized["batch"] = batch_id

    if semester is not None:
        try:
            semester = int(semester)
            sanitized["semester"] = semester
        except (ValueError, TypeError):
            pass

    # 2. Build StudentProfile base QuerySet constrained by ScopeContext
    students_qs = StudentProfile.objects.all()

    if scope_ctx.scope_level == "school":
        students_qs = students_qs.filter(course__department__school_id__in=scope_ctx.allowed_school_ids)
    elif scope_ctx.scope_level == "department":
        students_qs = students_qs.filter(course__department_id__in=scope_ctx.allowed_department_ids)
    elif scope_ctx.scope_level == "teacher":
        students_qs = students_qs.filter(batch_id__in=scope_ctx.allowed_batch_ids)

    # 3. Apply validated filters
    if school_id is not None:
        students_qs = students_qs.filter(course__department__school_id=school_id)
    if department_id is not None:
        students_qs = students_qs.filter(course__department_id=department_id)
    if course_id is not None:
        students_qs = students_qs.filter(course_id=course_id)
    if batch_id is not None:
        students_qs = students_qs.filter(batch_id=batch_id)

    return students_qs, sanitized


def get_analytics_overview(scope_ctx: ScopeContext, filters: dict) -> dict:
    """
    Computes top-level KPI overview strictly using database ORM aggregation.
    Bounded query count, zero student-by-student Python loops.
    """
    students_qs, sanitized = validate_and_filter_students(scope_ctx, filters)
    semester = sanitized.get("semester")

    # 1. Total Students
    total_students = students_qs.count()

    # 2. Semester Results (Pass Rate & Average Percentage)
    sem_qs = SemesterResult.objects.filter(is_published=True, student__in=students_qs)
    if semester is not None:
        sem_qs = sem_qs.filter(semester=semester)

    sem_agg = sem_qs.aggregate(
        total_count=Count("id"),
        passed_count=Count(
            "id",
            filter=~Q(Q(sgpa__lt=4.0) | Q(result_status="FAIL") | Q(percentage__lt=40.0)),
        ),
        avg_percentage=Avg("percentage"),
    )

    total_sem = sem_agg["total_count"] or 0
    passed_sem = sem_agg["passed_count"] or 0
    pass_rate = round((passed_sem / total_sem) * 100, 1) if total_sem > 0 else 0.0
    average_percentage = round(sem_agg["avg_percentage"] or 0.0, 1)

    # 3. Published Share (Published vs Total Semester Results)
    all_sem_qs = SemesterResult.objects.filter(student__in=students_qs)
    if semester is not None:
        all_sem_qs = all_sem_qs.filter(semester=semester)

    pub_agg = all_sem_qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(is_published=True)),
    )
    total_records = pub_agg["total"] or 0
    pub_records = pub_agg["published"] or 0
    published_share = round((pub_records / total_records) * 100, 1) if total_records > 0 else 0.0

    # 4. At-Risk Count & Rate (from latest PredictionSnapshot per student)
    latest_snap_id = Subquery(
        PredictionSnapshot.objects.filter(student=OuterRef("student_id"))
        .order_by("-taken_at", "-id")
        .values("id")[:1]
    )
    latest_snaps = PredictionSnapshot.objects.filter(
        student__in=students_qs,
        id=latest_snap_id,
    )
    if semester is not None:
        latest_snaps = latest_snaps.filter(semester=semester)

    at_risk_count = latest_snaps.filter(risk_band__in=["high", "insufficient_data"]).count()
    at_risk_rate = round((at_risk_count / total_students) * 100, 1) if total_students > 0 else 0.0

    # 5. Active Model Details
    active_model = ModelVersion.objects.filter(is_active=True).first()
    model_data = (
        {
            "slot": active_model.slot,
            "version": active_model.version,
            "algorithm": active_model.metrics.get("algorithm", "GradientBoostingRegressor")
            if active_model.metrics
            else "GradientBoostingRegressor",
            "metrics": active_model.metrics or {},
            "is_active": True,
        }
        if active_model
        else None
    )

    return {
        "total_students": total_students,
        "pass_rate": pass_rate,
        "average_percentage": average_percentage,
        "at_risk_count": at_risk_count,
        "at_risk_rate": at_risk_rate,
        "published_share": published_share,
        "model": model_data,
    }


ALLOWED_BREAKDOWN_LEVELS = {
    "university": {"school", "department", "course", "batch", "subject", "teacher"},
    "school": {"department", "course", "batch", "subject", "teacher"},
    "department": {"course", "batch", "subject", "teacher"},
    "teacher": {"batch", "subject"},
}


def get_analytics_breakdown(scope_ctx: ScopeContext, by_level: str, filters: dict) -> dict:
    """
    Computes cohort performance breakdown strictly by levels below user's scope.
    Applies differential privacy masking (groups < ANALYTICS_MIN_GROUP_SIZE merged into 'Other (hidden)').
    """
    students_qs, sanitized = validate_and_filter_students(scope_ctx, filters)
    semester = sanitized.get("semester")

    allowed_levels = ALLOWED_BREAKDOWN_LEVELS.get(scope_ctx.scope_level, set())
    if by_level not in allowed_levels:
        raise PermissionDenied(f"Breakdown level '{by_level}' is outside your authorized scope.")

    min_group_size = getattr(settings, "ANALYTICS_MIN_GROUP_SIZE", 10)

    # Route aggregation according to entity
    if by_level == "school":
        qs = (
            SemesterResult.objects.filter(is_published=True, student__in=students_qs)
            .values(
                entity_id=F("student__course__department__school__id"),
                entity_name=F("student__course__department__school__name"),
                entity_code=F("student__course__department__school__code"),
            )
        )
    elif by_level == "department":
        qs = (
            SemesterResult.objects.filter(is_published=True, student__in=students_qs)
            .values(
                entity_id=F("student__course__department__id"),
                entity_name=F("student__course__department__name"),
                entity_code=F("student__course__department__code"),
            )
        )
    elif by_level == "course":
        qs = (
            SemesterResult.objects.filter(is_published=True, student__in=students_qs)
            .values(
                entity_id=F("student__course__id"),
                entity_name=F("student__course__name"),
                entity_code=F("student__course__code"),
            )
        )
    elif by_level == "batch":
        qs = (
            SemesterResult.objects.filter(is_published=True, student__in=students_qs)
            .values(
                entity_id=F("student__batch__id"),
                entity_name=F("student__batch__batch_code"),
                entity_code=F("student__batch__batch_code"),
            )
        )
    elif by_level == "subject":
        res_qs = Result.objects.filter(student__in=students_qs)
        if scope_ctx.scope_level == "teacher":
            res_qs = res_qs.filter(subject_id__in=scope_ctx.allowed_subject_ids)
        if semester is not None:
            res_qs = res_qs.filter(semester=semester)

        raw_groups = (
            res_qs.values(
                entity_id=F("subject__id"),
                entity_name=F("subject__title"),
                entity_code=F("subject__code"),
            )
            .annotate(
                student_count=Count("student_id", distinct=True),
                total_results=Count("id"),
                pass_count=Count("id", filter=Q(total_secured__gte=40)),
                avg_pct=Avg("total_secured"),
            )
            .order_by("entity_name")
        )
        return _format_and_mask_breakdown(by_level, raw_groups, min_group_size)
    elif by_level == "teacher":
        res_qs = Result.objects.filter(student__in=students_qs, teacher__isnull=False)
        if semester is not None:
            res_qs = res_qs.filter(semester=semester)

        raw_groups = (
            res_qs.values(
                entity_id=F("teacher__id"),
                entity_name=F("teacher__staff_id"),
                entity_code=F("teacher__staff_id"),
            )
            .annotate(
                student_count=Count("student_id", distinct=True),
                total_results=Count("id"),
                pass_count=Count("id", filter=Q(total_secured__gte=40)),
                avg_pct=Avg("total_secured"),
            )
            .order_by("entity_name")
        )
        return _format_and_mask_breakdown(by_level, raw_groups, min_group_size)

    # For SemesterResult-based breakdown (school, department, course, batch)
    if semester is not None:
        qs = qs.filter(semester=semester)

    raw_groups = (
        qs.annotate(
            student_count=Count("student_id", distinct=True),
            total_results=Count("id"),
            pass_count=Count(
                "id",
                filter=~Q(Q(sgpa__lt=4.0) | Q(result_status="FAIL") | Q(percentage__lt=40.0)),
            ),
            avg_pct=Avg("percentage"),
        )
        .order_by("entity_name")
    )

    return _format_and_mask_breakdown(by_level, raw_groups, min_group_size)


def _format_and_mask_breakdown(by_level: str, raw_groups, min_group_size: int) -> dict:
    """
    Applies differential privacy masking.
    Any group with student_count < min_group_size is merged into 'Other (hidden)'.
    """
    visible_groups = []
    hidden_count = 0
    hidden_results = 0
    hidden_passes = 0
    hidden_pct_sum = 0.0

    for g in raw_groups:
        s_count = g["student_count"]
        t_results = g["total_results"]
        p_count = g["pass_count"]
        avg_p = float(g["avg_pct"] or 0.0)

        if s_count < min_group_size:
            hidden_count += s_count
            hidden_results += t_results
            hidden_passes += p_count
            hidden_pct_sum += avg_p * t_results
        else:
            p_rate = round((p_count / t_results) * 100, 1) if t_results > 0 else 0.0
            visible_groups.append(
                {
                    "id": g["entity_id"],
                    "name": g["entity_name"] or "Unknown",
                    "code": g["entity_code"] or "",
                    "student_count": s_count,
                    "pass_rate": p_rate,
                    "average_percentage": round(avg_p, 1),
                }
            )

    if hidden_count > 0:
        hidden_pass_rate = round((hidden_passes / hidden_results) * 100, 1) if hidden_results > 0 else 0.0
        hidden_avg_pct = round(hidden_pct_sum / hidden_results, 1) if hidden_results > 0 else 0.0
        visible_groups.append(
            {
                "id": None,
                "name": "Other (hidden)",
                "code": "OTHER",
                "student_count": hidden_count,
                "pass_rate": hidden_pass_rate,
                "average_percentage": hidden_avg_pct,
            }
        )

    return {
        "by": by_level,
        "groups": visible_groups,
    }


def get_analytics_trend(scope_ctx: ScopeContext, metric: str, filters: dict) -> dict:
    """
    Computes longitudinal performance trend per semester using database aggregation.
    Metric must be one of: 'pass_rate', 'avg_percentage', 'at_risk_rate'.
    """
    students_qs, sanitized = validate_and_filter_students(scope_ctx, filters)

    points = []

    if metric in ("pass_rate", "avg_percentage"):
        sem_qs = (
            SemesterResult.objects.filter(is_published=True, student__in=students_qs)
            .values("semester")
            .annotate(
                total_results=Count("id"),
                passed_results=Count(
                    "id",
                    filter=~Q(Q(sgpa__lt=4.0) | Q(result_status="FAIL") | Q(percentage__lt=40.0)),
                ),
                avg_percentage=Avg("percentage"),
                sample_size=Count("student_id", distinct=True),
            )
            .order_by("semester")
        )

        for row in sem_qs:
            sem = row["semester"]
            total = row["total_results"]
            sample_size = row["sample_size"]
            if metric == "pass_rate":
                val = round((row["passed_results"] / total) * 100, 1) if total > 0 else 0.0
            else:
                val = round(row["avg_percentage"] or 0.0, 1)

            points.append(
                {
                    "semester": sem,
                    "value": val,
                    "sample_size": sample_size,
                }
            )

    elif metric == "at_risk_rate":
        snap_qs = (
            PredictionSnapshot.objects.filter(student__in=students_qs)
            .values("semester")
            .annotate(
                total_students=Count("student_id", distinct=True),
                at_risk_students=Count(
                    "student_id",
                    distinct=True,
                    filter=Q(risk_band__in=["high", "insufficient_data"]),
                ),
            )
            .order_by("semester")
        )

        for row in snap_qs:
            sem = row["semester"]
            total = row["total_students"]
            at_risk = row["at_risk_students"]
            val = round((at_risk / total) * 100, 1) if total > 0 else 0.0
            points.append(
                {
                    "semester": sem,
                    "value": val,
                    "sample_size": total,
                }
            )
    else:
        raise PermissionDenied(f"Unknown metric '{metric}'.")

    return {
        "metric": metric,
        "points": points,
    }


def get_analytics_distribution(scope_ctx: ScopeContext, subject_id: int, filters: dict) -> dict:
    """
    Computes percentage score histogram with fixed bins in a single database ORM query.
    """
    if not scope_ctx.is_university_wide and subject_id not in scope_ctx.allowed_subject_ids:
        raise PermissionDenied("Requested subject is outside your authorized academic scope.")

    subject = Subject.objects.filter(id=subject_id).first()
    if not subject:
        raise PermissionDenied("Subject not found.")

    students_qs, sanitized = validate_and_filter_students(scope_ctx, filters)
    semester = sanitized.get("semester")
    batch_id = sanitized.get("batch")

    results_qs = Result.objects.filter(subject=subject, student__in=students_qs)
    if semester is not None:
        results_qs = results_qs.filter(semester=semester)
    if batch_id is not None:
        results_qs = results_qs.filter(batch_id=batch_id)

    results_qs = results_qs.annotate(
        calculated_pct=ExpressionWrapper(
            F("total_secured") * 100.0 / Case(
                When(max_marks__gt=0, then=F("max_marks")),
                default=Value(100),
                output_field=FloatField(),
            ),
            output_field=FloatField(),
        )
    )

    bins_agg = results_qs.aggregate(
        total=Count("id"),
        bin_0_39=Count(Case(When(calculated_pct__lt=40.0, then=1), output_field=IntegerField())),
        bin_40_49=Count(Case(When(calculated_pct__gte=40.0, calculated_pct__lt=50.0, then=1), output_field=IntegerField())),
        bin_50_59=Count(Case(When(calculated_pct__gte=50.0, calculated_pct__lt=60.0, then=1), output_field=IntegerField())),
        bin_60_69=Count(Case(When(calculated_pct__gte=60.0, calculated_pct__lt=70.0, then=1), output_field=IntegerField())),
        bin_70_79=Count(Case(When(calculated_pct__gte=70.0, calculated_pct__lt=80.0, then=1), output_field=IntegerField())),
        bin_80_89=Count(Case(When(calculated_pct__gte=80.0, calculated_pct__lt=90.0, then=1), output_field=IntegerField())),
        bin_90_100=Count(Case(When(calculated_pct__gte=90.0, then=1), output_field=IntegerField())),
    )

    bins = [
        {"label": "<40%", "min": 0, "max": 39, "count": bins_agg["bin_0_39"] or 0},
        {"label": "40-49%", "min": 40, "max": 49, "count": bins_agg["bin_40_49"] or 0},
        {"label": "50-59%", "min": 50, "max": 59, "count": bins_agg["bin_50_59"] or 0},
        {"label": "60-69%", "min": 60, "max": 69, "count": bins_agg["bin_60_69"] or 0},
        {"label": "70-79%", "min": 70, "max": 79, "count": bins_agg["bin_70_79"] or 0},
        {"label": "80-89%", "min": 80, "max": 89, "count": bins_agg["bin_80_89"] or 0},
        {"label": "90-100%", "min": 90, "max": 100, "count": bins_agg["bin_90_100"] or 0},
    ]

    return {
        "subject": {
            "id": subject.id,
            "code": subject.code,
            "title": subject.title,
        },
        "total_records": bins_agg["total"] or 0,
        "bins": bins,
    }


def get_at_risk_snapshots_queryset(scope_ctx: ScopeContext, filters: dict):
    """
    Returns QuerySet of latest PredictionSnapshots for students classified as at-risk
    within the caller's authorized scope.
    """
    students_qs, sanitized = validate_and_filter_students(scope_ctx, filters)
    semester = sanitized.get("semester")

    latest_id_subquery = Subquery(
        PredictionSnapshot.objects.filter(student=OuterRef("student_id"))
        .order_by("-taken_at", "-id")
        .values("id")[:1]
    )

    qs = (
        PredictionSnapshot.objects.filter(
            id=latest_id_subquery,
            student__in=students_qs,
            risk_band__in=["high", "insufficient_data"],
        )
        .select_related(
            "student",
            "student__user",
            "student__batch",
            "student__course",
            "subject",
        )
        .order_by("predicted_percentage", "-taken_at", "id")
    )

    if semester is not None:
        qs = qs.filter(semester=semester)

    return qs
