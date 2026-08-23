"""URL map for the 'accounts' app."""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("my-results/", views.my_results, name="my_results"),
    path("results-overview/", views.scoped_results, name="scoped_results"),
    path("my-predictions/", views.my_predictions, name="my_predictions"),
    path("at-risk/", views.at_risk_students, name="at_risk_students"),
]
