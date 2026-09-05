"""
Automated Verification Suite for Hierarchical Dashboards and Internal Assessment Workflow.
"""
import os
import sys
import django
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile

# Configure Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resultplatform.settings")
django.setup()

from accounts.models import User
from accounts.views import home, teacher_internal_marks, my_results
from academics.models import (
    SemesterResult, InternalAssessment, TeachingAssignment, StudentProfile
)
from academics.admin import SemesterResultAdmin
from django.contrib.admin.sites import AdminSite

def test_role_dashboards():
    print("=== TEST 1: Hierarchical Role Dashboards ===")
    factory = RequestFactory()
    
    test_cases = [
        ("STUDENT", "cse_stu01"),
        ("TEACHER", "cse_fac01"),
        ("HOD", "hod_cse"),
        ("DEAN", "dean_engg"),
        ("VC", "vc"),
        ("SYSTEM_ADMIN", "Aman_Yadav"),
    ]
    
    for role, username in test_cases:
        user = User.objects.filter(username=username).first()
        if not user:
            # Fallback to any user with role
            user = User.objects.filter(role=role).first()
            
        assert user is not None, f"User for role {role} not found"
        
        req = factory.get("/")
        req.user = user
        setattr(req, "session", {})
        setattr(req, "_messages", FallbackStorage(req))
        
        response = home(req)
        assert response.status_code == 200, f"Dashboard failed for {role}: status {response.status_code}"
        content = response.content.decode("utf-8")
        
        # Verify Rule of 3 KPIs in HTML
        assert "grid-kpi-3" in content, f"Grid 3 KPIs not found in HTML for {role}"
        assert "kpi-card" in content, f"KPI cards missing for {role}"
        print(f"  [PASS] Role '{role}' ({user.username}): HTTP 200 & 3-KPI grid verified")

def test_teacher_internal_marks_flow():
    print("\n=== TEST 2: Teacher Internal Marks Entry & CSV Upload ===")
    factory = RequestFactory()
    teacher_user = User.objects.filter(role="TEACHER").first()
    assert teacher_user is not None
    
    teacher_profile = teacher_user.teacher_profile
    assignment = TeachingAssignment.objects.filter(teacher=teacher_profile).first()
    if not assignment:
        assignment = TeachingAssignment.objects.first()
        assignment.teacher = teacher_profile
        assignment.save()
        
    student = assignment.batch.students.first()
    assert student is not None, "No student in batch"

    # 1. Test GET view
    req = factory.get(f"/teacher/internal-marks/?assignment={assignment.id}")
    req.user = teacher_user
    setattr(req, "session", {})
    setattr(req, "_messages", FallbackStorage(req))
    resp = teacher_internal_marks(req)
    assert resp.status_code == 200
    print(f"  [PASS] Teacher marks portal GET: HTTP 200")

    # 2. Test POST inline entry
    post_data = {
        "title": "Unit Test 1 - Automated",
        "assessment_type": "QUIZ",
        "max_marks": "25.0",
        f"marks_{student.id}": "22.5",
    }
    req_post = factory.post(f"/teacher/internal-marks/?assignment={assignment.id}", post_data)
    req_post.user = teacher_user
    setattr(req_post, "session", {})
    setattr(req_post, "_messages", FallbackStorage(req_post))
    resp_post = teacher_internal_marks(req_post)
    assert resp_post.status_code == 302, f"Expected redirect, got {resp_post.status_code}"
    
    created_record = InternalAssessment.objects.filter(
        student=student, subject=assignment.subject, title="Unit Test 1 - Automated"
    ).first()
    assert created_record is not None, "Internal assessment record was not created"
    assert created_record.marks_obtained == 22.5
    print(f"  [PASS] Inline marks submission created record: {created_record.marks_obtained}/{created_record.max_marks}")

    # 3. Test POST CSV bulk upload
    csv_content = f"roll_no,marks\n{student.roll_no},24.0\n"
    csv_file = SimpleUploadedFile("marks.csv", csv_content.encode("utf-8"), content_type="text/csv")
    req_csv = factory.post(
        f"/teacher/internal-marks/?assignment={assignment.id}",
        {"title": "CSV Midterm Upload", "assessment_type": "MIDTERM", "max_marks": "30.0", "csv_file": csv_file}
    )
    req_csv.user = teacher_user
    setattr(req_csv, "session", {})
    setattr(req_csv, "_messages", FallbackStorage(req_csv))
    resp_csv = teacher_internal_marks(req_csv)
    assert resp_csv.status_code == 302
    
    csv_record = InternalAssessment.objects.filter(
        student=student, subject=assignment.subject, title="CSV Midterm Upload"
    ).first()
    assert csv_record is not None, "CSV assessment record not created"
    assert csv_record.marks_obtained == 24.0
    print(f"  [PASS] CSV file upload created record: {csv_record.marks_obtained}/{csv_record.max_marks}")

def test_admin_publish_action():
    print("\n=== TEST 3: Admin Publish / Unpublish Action ===")
    sem_res = SemesterResult.objects.first()
    assert sem_res is not None
    
    # Revert to draft
    sem_res.is_published = False
    sem_res.save()
    
    # Test admin publish action
    admin_instance = SemesterResultAdmin(SemesterResult, AdminSite())
    queryset = SemesterResult.objects.filter(id=sem_res.id)
    
    factory = RequestFactory()
    req = factory.get("/")
    req.user = User.objects.filter(is_superuser=True).first()
    setattr(req, "session", {})
    setattr(req, "_messages", FallbackStorage(req))
    
    admin_instance.publish_final_results(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published == True, "publish_final_results action did not set is_published=True"
    print(f"  [PASS] Admin publish action successfully released SemesterResult #{sem_res.id}")

    admin_instance.revert_to_draft(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published == False, "revert_to_draft did not set is_published=False"
    print(f"  [PASS] Admin revert_to_draft successfully held SemesterResult #{sem_res.id}")
    
    # Re-publish for system consistency
    sem_res.is_published = True
    sem_res.save()

if __name__ == "__main__":
    test_role_dashboards()
    test_teacher_internal_marks_flow()
    test_admin_publish_action()
    print("\n=======================================================")
    print("ALL VERIFICATION TESTS PASSED PERFECTLY!")
    print("=======================================================")
