"""
Create sample users for local development.

Run with: python manage.py shell < scripts/seed_sample_users.py
"""

import os
import sys

demo_password = os.environ.get("DEMO_USER_PASSWORD")
if not demo_password:
    print("ERROR: DEMO_USER_PASSWORD environment variable is required.", file=sys.stderr)
    sys.exit(1)

from accounts.models import User

# (username, password, role, first_name, last_name, email, is_staff, is_superuser)
SAMPLE_USERS = [
    ("admin",      demo_password, User.Role.SYSADMIN,    "System", "Admin",  "admin@adu.edu.in",   True,  True),
    ("vc",         demo_password, User.Role.VC,          "Ishaan", "Sharma", "vc@adu.edu.in",      True,  False),
    ("dean_engg",  demo_password, User.Role.DEAN,        "Tara",   "Iyer",   "dean@adu.edu.in",    True,  False),
    ("hod_cse",    demo_password, User.Role.HOD,         "Shreya", "Mehta",  "hod@adu.edu.in",     True,  False),
    ("teacher_cse",demo_password, User.Role.TEACHER,     "Vikram", "Kumar",  "teacher@adu.edu.in", True,  False),
    ("student_cs", demo_password, User.Role.STUDENT,     "Nisha",  "Das",    "nisha@student.adu.edu.in", False, False),
]

print("\nSeeding sample users...")
for username, pw, role, fn, ln, email, is_staff, is_super in SAMPLE_USERS:
    user, created = User.objects.get_or_create(
        username=username,
        defaults=dict(role=role, first_name=fn, last_name=ln, email=email,
                      is_staff=is_staff, is_superuser=is_super),
    )
    # always (re)set the password and role so re-running stays consistent
    user.role = role
    user.is_staff = is_staff
    user.is_superuser = is_super
    user.set_password(pw)   # set_password hashes it correctly — never store plain text
    user.save()
    status = "created" if created else "updated"
    print(f"  [{status}] {username:12s} -> {user.get_role_display()}")

print(f"\nDone. Total users now: {User.objects.count()}")
print("Login at /admin with superuser username: admin.")

