from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model supporting institutional role hierarchy and scoped access control.
    """

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

    # Contact details
    phone = models.CharField(max_length=15, blank=True)

    # Demographic and profile fields
    dob = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    address_city = models.CharField(max_length=60, blank=True)
    address_state = models.CharField(max_length=60, blank=True)
    category = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, default="active", blank=True)

    # Scope assignment fields for department- and school-level roles
    department = models.ForeignKey("academics.Department", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="staff_members")
    school = models.ForeignKey("academics.School", on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="staff_members")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

