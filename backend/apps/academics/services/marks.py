"""
Service functions for continuous internal assessment and marks processing.
"""

import csv
import io
from typing import Any, Tuple
from academics.models import InternalAssessment, StudentProfile


def process_internal_marks_csv(
    assignment: Any,
    teacher: Any,
    semester: int,
    title: str,
    assessment_type: str,
    max_marks: float,
    csv_file: Any,
) -> Tuple[int, str | None]:
    """
    Parses an uploaded CSV file and creates InternalAssessment records.
    Returns (saved_count, error_message).
    """
    saved_count = 0
    try:
        decoded_file = csv_file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        for row in reader:
            keys = {k.lower().strip(): k for k in row.keys()}
            roll_key = keys.get("roll_no") or keys.get("roll") or keys.get("student_id") or keys.get("rollno")
            marks_key = keys.get("marks") or keys.get("marks_obtained") or keys.get("score")
            if roll_key and marks_key and row[roll_key] and row[marks_key]:
                roll = row[roll_key].strip()
                try:
                    marks = float(row[marks_key].strip())
                except ValueError:
                    continue
                st = StudentProfile.objects.filter(roll_no=roll).first()
                if st:
                    InternalAssessment.objects.create(
                        student=st,
                        subject=assignment.subject,
                        batch=assignment.batch,
                        teacher=teacher,
                        semester=semester,
                        title=title,
                        assessment_type=assessment_type,
                        marks_obtained=min(marks, max_marks),
                        max_marks=max_marks,
                        is_submitted=True,
                    )
                    saved_count += 1
        return saved_count, None
    except Exception as e:
        return 0, str(e)


def process_internal_marks_form(
    assignment: Any,
    teacher: Any,
    semester: int,
    title: str,
    assessment_type: str,
    max_marks: float,
    students: Any,
    post_data: Any,
) -> int:
    """
    Saves individual student marks from HTML form inputs.
    Returns saved_count.
    """
    saved_count = 0
    for st in students:
        mark_val = post_data.get(f"marks_{st.id}")
        if mark_val is not None and mark_val.strip() != "":
            try:
                marks = float(mark_val.strip())
            except ValueError:
                continue
            InternalAssessment.objects.create(
                student=st,
                subject=assignment.subject,
                batch=assignment.batch,
                teacher=teacher,
                semester=semester,
                title=title,
                assessment_type=assessment_type,
                marks_obtained=min(marks, max_marks),
                max_marks=max_marks,
                is_submitted=True,
            )
            saved_count += 1
    return saved_count
