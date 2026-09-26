"""
Tests for Django Admin publication actions and administrative workflows.
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from academics.admin import SemesterResultAdmin
from academics.models import SemesterResult
from tests.factories import make_university


@pytest.mark.django_db
def test_admin_publish_and_revert_actions():
    """
    Verify Django admin actions for bulk result publishing and reverting to draft.
    """
    tree = make_university(students_per_batch=2)
    admin_user = tree["executives"]["admin"]
    student = tree["students"][0]

    sem_res = SemesterResult.objects.filter(student=student, semester=1).first()
    assert sem_res is not None
    sem_res.is_published = False
    sem_res.save()

    admin_instance = SemesterResultAdmin(SemesterResult, AdminSite())
    queryset = SemesterResult.objects.filter(id=sem_res.id)

    factory = RequestFactory()
    req = factory.get("/")
    req.user = admin_user
    setattr(req, "session", {})
    setattr(req, "_messages", FallbackStorage(req))

    # Test publish
    admin_instance.publish_final_results(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published is True

    # Test revert to draft
    admin_instance.revert_to_draft(req, queryset)
    sem_res.refresh_from_db()
    assert sem_res.is_published is False
