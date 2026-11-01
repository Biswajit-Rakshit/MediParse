from django.urls import path
from apps.extraction.views import ExtractedRecordListView

urlpatterns = [
    path("", ExtractedRecordListView.as_view(), name="extraction-list"),
]