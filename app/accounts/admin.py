from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Registers our custom User in the admin panel.

    We reuse Django's built-in UserAdmin (so we keep the nice password handling,
    permissions screen, etc.) and just add our `role` and `phone` fields so the
    admin can see and edit them.
    """

    # Columns shown in the user list
    list_display = ("username", "full_name_or_username", "role", "email", "is_staff")
    list_filter = ("role", "is_staff", "is_active")

    # Add our extra fields into the edit form (appended to Django's default sections)
    fieldsets = UserAdmin.fieldsets + (
        ("Result Platform info", {"fields": ("role", "phone")}),
    )
    # And into the "add new user" form
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Result Platform info", {"fields": ("role", "phone")}),
    )

    @admin.display(description="Name")
    def full_name_or_username(self, obj):
        return obj.get_full_name() or obj.username
