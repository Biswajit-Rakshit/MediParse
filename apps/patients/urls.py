from django.urls import path
from apps.patients.views import PatientListCreateView, PatientDetailView

urlpatterns = [
    path("", PatientListCreateView.as_view(), name="patient-list-create"),
    path("<uuid:pk>/", PatientDetailView.as_view(), name="patient-detail"),
]