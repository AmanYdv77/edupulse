"""
Tests for database CheckConstraints, Indexes, and Migration Reversibility (Task A21).
Validates that invalid values are rejected by the database (PostgreSQL IntegrityError)
and exact boundary values are accepted.
"""

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from academics.models import Result, SemesterResult, HabitCheckInLog
from tests.factories import (
    StudentProfileFactory,
    SubjectFactory,
    BatchFactory,
    TeacherProfileFactory,
)


@pytest.mark.django_db(transaction=True)
class TestResultConstraints:
    """Verifies check_result_total_secured_range on academics.Result."""

    def test_result_boundary_values_accepted(self):
        student = StudentProfileFactory()
        subject = SubjectFactory(max_marks=100)
        
        # Lower boundary: 0
        r_min = Result.objects.create(
            student=student,
            subject=subject,
            semester=1,
            total_secured=0,
            max_marks=100,
        )
        assert r_min.total_secured == 0

        # Upper boundary: max_marks
        subject_2 = SubjectFactory(code="CS102", max_marks=100)
        r_max = Result.objects.create(
            student=student,
            subject=subject_2,
            semester=1,
            total_secured=100,
            max_marks=100,
        )
        assert r_max.total_secured == 100

    def test_result_negative_secured_rejected(self):
        student = StudentProfileFactory()
        subject = SubjectFactory(max_marks=100)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Result.objects.create(
                    student=student,
                    subject=subject,
                    semester=1,
                    total_secured=-1,
                    max_marks=100,
                )

    def test_result_secured_exceeding_max_marks_rejected(self):
        student = StudentProfileFactory()
        subject = SubjectFactory(max_marks=100)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Result.objects.create(
                    student=student,
                    subject=subject,
                    semester=1,
                    total_secured=105,
                    max_marks=100,
                )

    def test_result_non_positive_max_marks_rejected(self):
        student = StudentProfileFactory()
        subject = SubjectFactory(max_marks=100)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Result.objects.create(
                    student=student,
                    subject=subject,
                    semester=1,
                    total_secured=0,
                    max_marks=0,
                )


@pytest.mark.django_db(transaction=True)
class TestSemesterResultConstraints:
    """Verifies CheckConstraints on academics.SemesterResult."""

    def test_percentage_boundaries_and_rejection(self):
        student = StudentProfileFactory()

        # Lower and upper boundary
        sr1 = SemesterResult.objects.create(student=student, semester=1, percentage=0.0)
        assert sr1.percentage == 0.0

        sr2 = SemesterResult.objects.create(student=student, semester=2, percentage=100.0)
        assert sr2.percentage == 100.0

        # Rejection < 0.0
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=3, percentage=-0.1)

        # Rejection > 100.0
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=4, percentage=100.5)

    def test_attendance_boundaries_and_rejection(self):
        student = StudentProfileFactory()

        # Null allowed
        sr1 = SemesterResult.objects.create(student=student, semester=1, attendance_percentage=None)
        assert sr1.attendance_percentage is None

        # Boundaries 0 and 100
        sr2 = SemesterResult.objects.create(student=student, semester=2, attendance_percentage=0.0)
        assert sr2.attendance_percentage == 0.0

        sr3 = SemesterResult.objects.create(student=student, semester=3, attendance_percentage=100.0)
        assert sr3.attendance_percentage == 100.0

        # Out of bounds
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=4, attendance_percentage=-1.0)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=5, attendance_percentage=101.0)

    def test_sleep_and_study_boundaries_and_rejection(self):
        student = StudentProfileFactory()

        # Valid boundaries
        sr = SemesterResult.objects.create(
            student=student,
            semester=1,
            sleep_hours_per_night=24.0,
            hours_studied_per_week=168.0,
        )
        assert sr.sleep_hours_per_night == 24.0
        assert sr.hours_studied_per_week == 168.0

        # Sleep > 24 rejected
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=2, sleep_hours_per_night=24.5)

        # Study > 168 rejected
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SemesterResult.objects.create(student=student, semester=3, hours_studied_per_week=170.0)


@pytest.mark.django_db(transaction=True)
class TestHabitCheckInLogConstraints:
    """Verifies CheckConstraints on academics.HabitCheckInLog."""

    def test_sleep_hours_range(self):
        student = StudentProfileFactory()

        # Valid boundaries: 0 and 24
        log1 = HabitCheckInLog.objects.create(student=student, sleep_hours=0.0)
        assert log1.sleep_hours == 0.0

        log2 = HabitCheckInLog.objects.create(student=student, sleep_hours=24.0)
        assert log2.sleep_hours == 24.0

        # Invalid sleep
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HabitCheckInLog.objects.create(student=student, sleep_hours=-0.5)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HabitCheckInLog.objects.create(student=student, sleep_hours=24.5)

    def test_hours_studied_cadence_constraints(self):
        student = StudentProfileFactory()

        # DAILY: 0 to 24 accepted
        d_ok = HabitCheckInLog.objects.create(student=student, log_type="DAILY", hours_studied=24.0)
        assert d_ok.hours_studied == 24.0

        # DAILY > 24 rejected
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HabitCheckInLog.objects.create(student=student, log_type="DAILY", hours_studied=25.0)

        # WEEKLY: 0 to 168 accepted
        w_ok = HabitCheckInLog.objects.create(student=student, log_type="WEEKLY", hours_studied=168.0)
        assert w_ok.hours_studied == 168.0

        # WEEKLY > 168 rejected
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HabitCheckInLog.objects.create(student=student, log_type="WEEKLY", hours_studied=170.0)


@pytest.mark.django_db(transaction=True)
class TestIndexPresenceAndMigrationReversibility:
    """Verifies that all specified indexes exist and migration 0008 is reversible."""

    def test_named_indexes_exist_in_database(self):
        with connection.cursor() as cursor:
            indexes = connection.introspection.get_constraints(cursor, "academics_result")
            assert "idx_result_student_sem" in indexes
            assert "idx_result_subject_sem" in indexes

            sem_indexes = connection.introspection.get_constraints(cursor, "academics_semesterresult")
            assert "idx_semresult_pub_sem" in sem_indexes

            habit_indexes = connection.introspection.get_constraints(cursor, "academics_habitcheckinlog")
            assert "idx_habitlog_student_date" in habit_indexes

    def test_migration_reversibility(self):
        # Roll back to 0007
        call_command("migrate", "academics", "0007")

        # Verify rollback in database introspection
        with connection.cursor() as cursor:
            indexes = connection.introspection.get_constraints(cursor, "academics_result")
            assert "idx_result_student_sem" not in indexes

        # Roll forward to 0008
        call_command("migrate", "academics", "0008")

        # Verify restored in database introspection
        with connection.cursor() as cursor:
            indexes = connection.introspection.get_constraints(cursor, "academics_result")
            assert "idx_result_student_sem" in indexes
