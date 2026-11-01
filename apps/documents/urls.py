from django.urls import path
from apps.documents.views import DocumentListCreateView, DocumentDetailView
from apps.extraction.views import DocumentExtractionView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="document-list-create"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<uuid:pk>/extraction/", DocumentExtractionView.as_view(), name="document-extraction"),
]