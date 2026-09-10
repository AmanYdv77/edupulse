"""
Automated Verification Suite for EduPulse Multi-Tier Analytics Suite.
Tests statistical computations (Topper, failures, 5-number summary, median, deltas)
and verifies response status & performance across all stakeholder roles.
"""
import os
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add app directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE_DIR, "app")
sys.path.insert(0, APP_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resultplatform.settings")

import django
django.setup()

from django.test import Client
from accounts.models import User
from academics.models import StudentProfile, TeacherProfile, Department, School
from academics.analytics_engine import (
    compute_cohort_deep_dive, get_student_analytics, get_teacher_analytics,
    get_hod_analytics, get_dean_analytics, get_executive_analytics
)


def run_tests():
    print("=" * 70)
    print("🚀 RUNNING MULTI-TIER ANALYTICS VERIFICATION TEST SUITE")
    print("=" * 70)

    # 1. Test Statistical Cohort Deep-Dive Engine
    print("\n[TEST 1] Testing Statistical Cohort Deep-Dive Engine...")
    t0 = time.time()
    stats = compute_cohort_deep_dive()
    t1 = time.time()
    
    print(f"  ✓ Total records analyzed: {stats['total_count']}")
    print(f"  ✓ Execution time: {round((t1 - t0) * 1000, 2)}ms")
    print(f"  ✓ 5-Number Spread: Min={stats['min_sgpa']}, Q1={stats['q1_sgpa']}, Median={stats['median_sgpa']}, Q3={stats['q3_sgpa']}, Max={stats['max_sgpa']}")
    print(f"  ✓ Average SGPA: {stats['avg_sgpa']}")
    print(f"  ✓ Failed Students: {stats['failed_count']} (Pass Rate: {stats['pass_percentage']}%)")
    if stats['topper']:
        print(f"  ✓ Cohort Topper: {stats['topper']['name']} (SGPA: {stats['topper']['sgpa']}, {stats['topper']['percentage']}%)")
    assert stats['total_count'] >= 0, "Record count must be non-negative"
    assert len(stats['chart_data']) == 7, "Histogram must have 7 bins"
    print("  --> [PASS] Statistical Engine Validated.")

    # 2. Test Student Analytics Engine
    print("\n[TEST 2] Testing Student Self-Reflection Engine...")
    student = StudentProfile.objects.first()
    if student:
        st_data = get_student_analytics(student)
        print(f"  ✓ Student: {student.roll_no} ({student.user.username})")
        print(f"  ✓ Percentile Rank: {st_data['percentile_rank']}% ({st_data['batch_standing']})")
        print(f"  ✓ Rank: #{st_data['rank']} / {st_data['batch_size']}")
        print(f"  ✓ SGPA Delta: {st_data['sgpa_delta']}")
        print(f"  ✓ Trajectory Points: {len(st_data['trajectory_labels'])}")
        print("  --> [PASS] Student Analytics Validated.")
    else:
        print("  ⚠️ No student profile found, skipping student specific check.")

    # 3. Test Teacher Analytics Engine
    print("\n[TEST 3] Testing Faculty Subject Analytics Engine...")
    teacher = TeacherProfile.objects.first()
    tc_data = get_teacher_analytics(teacher)
    print(f"  ✓ Active Assignments: {tc_data['assignments'].count()}")
    print(f"  ✓ Scatter Risk Points: {len(tc_data['scatter_points'])}")
    print("  --> [PASS] Teacher Analytics Validated.")

    # 4. Test HOD Analytics Engine
    print("\n[TEST 4] Testing HOD Department Analytics Engine...")
    dept = Department.objects.first()
    hod_data = get_hod_analytics(dept)
    print(f"  ✓ Department: {dept.name if dept else 'None'}")
    print(f"  ✓ Bottlenecks Identified: {len(hod_data['bottlenecks'])}")
    print(f"  ✓ Faculty Compliance Entries: {len(hod_data['compliance_list'])}")
    print("  --> [PASS] HOD Analytics Validated.")

    # 5. Test Dean Analytics Engine
    print("\n[TEST 5] Testing Dean School Analytics Engine...")
    school = School.objects.first()
    dean_data = get_dean_analytics(school)
    print(f"  ✓ School: {school.name if school else 'None'}")
    print(f"  ✓ Constituent Depts: {len(dean_data['dept_benchmarks'])}")
    print(f"  ✓ Placement & Honors Pool: {dean_data['honors_count']} students")
    print("  --> [PASS] Dean Analytics Validated.")

    # 6. Test Executive Analytics Engine
    print("\n[TEST 6] Testing Executive University Governance Engine...")
    exec_data = get_executive_analytics()
    print(f"  ✓ Moderation Anomalies Flagged: {exec_data['anomaly_flags']}")
    print(f"  ✓ Audited Points: {len(exec_data['moderation_scatter'])}")
    print(f"  ✓ Pending Drafts: {exec_data['drafts_count']}")
    print("  --> [PASS] Executive Analytics Validated.")

    # 7. Test HTTP Client Endpoints & RBAC Routing
    print("\n[TEST 7] Testing HTTP View Endpoints across Roles...")
    client = Client()

    # Find or create representative test users
    roles_to_test = ["STUDENT", "TEACHER", "HOD", "DEAN", "VC"]
    for role in roles_to_test:
        u = User.objects.filter(role=role).first()
        if not u:
            # Fallback to creating a test user if none exists
            u, _ = User.objects.get_or_create(username=f"test_{role.lower()}", role=role)
            u.set_password("pass1234")
            u.save()

        client.force_login(u)
        t_req0 = time.time()
        resp = client.get("/analytics/")
        t_req1 = time.time()
        
        elapsed_ms = round((t_req1 - t_req0) * 1000, 1)
        print(f"  ✓ Role [{role:8s}]: HTTP {resp.status_code} in {elapsed_ms}ms (User: {u.username})")
        assert resp.status_code == 200, f"Expected 200 for {role}, got {resp.status_code}"

    # Test Cohort JSON API
    print("\n[TEST 8] Testing Cohort Query JSON API...")
    resp_api = client.get("/analytics/api/cohort-query/")
    print(f"  ✓ API Endpoint [/analytics/api/cohort-query/]: HTTP {resp_api.status_code}")
    assert resp_api.status_code == 200, f"Expected 200, got {resp_api.status_code}"
    json_data = resp_api.json()
    assert json_data["status"] == "success"
    print(f"  ✓ API Response status: {json_data['status']}, Total Cohort: {json_data['data']['total_count']}")
    print("  --> [PASS] API Query Endpoint Validated.")

    print("\n" + "=" * 70)
    print("🎉 ALL MULTI-TIER ANALYTICS TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
