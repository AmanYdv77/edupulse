"""
Milestone 1 — create a FEW sample users so you can see the system working.

Run it with:   python manage.py shell < seed_sample_users.py

We deliberately create only ~6 users (not all 800) so you can understand each
one. Importing the full university.db comes in a later milestone.

All sample passwords are:  Pass@123   (fine for learning; never for real use)
"""

from accounts.models import User

# (username, password, role, first_name, last_name, email, is_staff, is_superuser)
SAMPLE_USERS = [
    ("admin",      "Pass@123", User.Role.SYSADMIN,    "System", "Admin",  "admin@adu.edu.in",   True,  True),
    ("vc",         "Pass@123", User.Role.VC,          "Ishaan", "Sharma", "vc@adu.edu.in",      True,  False),
    ("dean_engg",  "Pass@123", User.Role.DEAN,        "Tara",   "Iyer",   "dean@adu.edu.in",    True,  False),
    ("hod_cse",    "Pass@123", User.Role.HOD,         "Shreya", "Mehta",  "hod@adu.edu.in",     True,  False),
    ("teacher_cse","Pass@123", User.Role.TEACHER,     "Vikram", "Kumar",  "teacher@adu.edu.in", True,  False),
    ("student_cs", "Pass@123", User.Role.STUDENT,     "Nisha",  "Das",    "nisha@student.adu.edu.in", False, False),
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
print("Login at /admin with  admin / Pass@123  (the superuser).")
