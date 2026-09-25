"""
Dashboard views for EduPulse.
Delegates role telemetry loading to selectors.py so view functions remain concise (<30 lines).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from ..selectors import get_dashboard_context_for_role


def index(request):
    """
    Root URL handler:
    Always redirects to the login screen so users are not automatically locked
    into a previous session's dashboard.
    """
    return redirect("login")


@login_required
def home(request):
    """
    Unified entrypoint dashboard.
    Loads role-scoped telemetry, KPIs, and navigation cards through selectors.
    """
    context = get_dashboard_context_for_role(request.user)
    return render(request, "home.html", context)
