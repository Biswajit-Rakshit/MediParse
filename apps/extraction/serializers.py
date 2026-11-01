from rest_framework import serializers
from apps.extraction.models import ExtractedRecord


class ExtractedRecordSerializer(serializers.ModelSerializer):
    document_id = serializers.UUIDField(source="document.id", read_only=True)
    document_status = serializers.CharField(source="document.status", read_only=True)
    original_filename = serializers.CharField(source="document.original_filename", read_only=True)

    class Meta:
        model = ExtractedRecord
        fields = [
            "id",
            "document_id",
            "document_status",
            "original_filename",
            "patient_name",
            "dob",
            "visit_date",
            "doctor_name",
            "diagnosis",
            "medications",
            "lab_values",
            "confidence_score",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields