"""
Main URL map for the whole project.

This is the FRONT DOOR. It decides where each web address goes:
  - /admin/  -> the built-in admin panel
  - /accounts/login/ , /accounts/logout/  -> Django's built-in login system
  - everything else ("")  -> our 'accounts' app (the home page, etc.)
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Django's built-in login/logout pages (we just point our own template at them).
    path("accounts/", include("django.contrib.auth.urls")),

    # Our app's pages (home page lives at "/").
    path("", include("accounts.urls")),
]
