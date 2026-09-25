"""URL mapping for the predictions app."""

from django.urls import path
from . import views

urlpatterns = [
    path("my-predictions/", views.my_predictions, name="my_predictions"),
    path("at-risk/", views.at_risk_students, name="at_risk_students"),
]
