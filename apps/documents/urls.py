from django.urls import path
from apps.documents.views import DocumentListCreateView, DocumentDetailView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="document-list-create"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
]