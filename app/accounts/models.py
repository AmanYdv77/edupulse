from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Our custom user. It REUSES everything Django's built-in user already gives us
    (username, password, email, login system, security) and ADDS the fields our
    Result Platform needs — most importantly, a `role`.

    Why a custom user? Because every person in the system (VC, Dean, HOD, Teacher,
    Student) logs in the same way but should SEE different data. The `role` field
    is what later lets us filter "who sees what" (our hierarchy).

    IMPORTANT: a custom user must be set BEFORE the first migrate. That's exactly
    why we are doing this in Milestone 1, first thing.
    """

    # ---- The roles in our university (matches DATABASE_DESIGN.md) ----
    class Role(models.TextChoices):
        VC = "VC", "Vice Chancellor"
        REGISTRAR = "REGISTRAR", "Registrar"
        CONTROLLER = "CONTROLLER_OF_EXAMS", "Controller of Examinations"
        SYSADMIN = "SYSTEM_ADMIN", "System Administrator"
        DEAN = "DEAN", "Dean"
        HOD = "HOD", "Head of Department"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Decides what this user is allowed to see.",
    )

    # ---- A few shared contact/personal fields (kept simple for Milestone 1) ----
    phone = models.CharField(max_length=15, blank=True)

    # ---- Richer personal fields (Milestone 6: imported from full dataset) ----
    dob = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    address_city = models.CharField(max_length=60, blank=True)
    address_state = models.CharField(max_length=60, blank=True)
    category = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, default="active", blank=True)

    # ---- Scope fields (Milestone 5): WHICH department/school this staff member
    #      belongs to. This is what powers "who sees what":
    #        HOD  -> sees their department
    #        Dean -> sees their school
    #      Students don't need these (their scope comes from their course).
    #      String references ("academics.X") avoid import problems.
    department = models.ForeignKey("academics.Department", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="staff_members")
    school = models.ForeignKey("academics.School", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="staff_members")

    # Note: full personal details, results etc. live in the academics app.

    def __str__(self):
        # This is what shows up in the admin panel and shell — nice and readable.
        return f"{self.username} ({self.get_role_display()})"
