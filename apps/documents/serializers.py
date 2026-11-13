from rest_framework import serializers
from typing import Optional

from apps.documents.models import Document
from common.s3 import generate_presigned_url


class DocumentUploadSerializer(serializers.Serializer):
    """Used for handling the incoming upload request."""
    file = serializers.FileField()
    patient = serializers.UUIDField()

    def validate_file(self, value):
        # Only allow PDF and images
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only PDF, JPEG and PNG files are allowed."
            )
        # Max file size 10MB
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                "File size must not exceed 10MB."
            )
        return value

    def validate_patient(self, value):
        from apps.patients.models import Patient
        request = self.context.get("request")
        try:
            patient = Patient.objects.get(
                pk=value,
                organization=request.user.organization
            )
        except Patient.DoesNotExist:
            raise serializers.ValidationError(
                "Patient not found in your organization."
            )
        return patient


class DocumentSerializer(serializers.ModelSerializer):
    """Used for returning document data in responses."""
    download_url = serializers.SerializerMethodField()
    uploaded_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "patient",
            "original_filename",
            "file_type",
            "status",
            "uploaded_by_email",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        return generate_presigned_url(obj.file_key)

    def get_uploaded_by_email(self, obj) -> Optional[str]:
        if obj.uploaded_by:
            return obj.uploaded_by.email