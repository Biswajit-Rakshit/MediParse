from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
import uuid

from apps.documents.models import Document
from apps.documents.serializers import DocumentUploadSerializer, DocumentSerializer
from apps.extraction.tasks import extract_document_task
from apps.audit.models import AuditLog
from apps.audit.utils import log_action

from common.permissions import IsDoctor, IsNurse
from common.schema import PAGE_PARAMS, paginated
from common.pagination import StandardPagination
from common.s3 import upload_file_to_s3
from common.throttles import UploadRateThrottle


class DocumentListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsDoctor()]
        return [IsNurse()]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == "POST":
            throttles.append(UploadRateThrottle())
        return throttles

    @extend_schema(
        operation_id="documents_list",
        tags=["Documents"],
        summary="List documents in your organization (nurse+)",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("status", str, enum=["uploaded", "processing", "completed", "failed"]),
            OpenApiParameter("file_type", str, enum=["pdf", "image"]),
            OpenApiParameter("patient", OpenApiTypes.UUID, description="Filter by patient id."),
        ],
        responses=paginated(DocumentSerializer),
    )
    def get(self, request):
        documents = Document.objects.filter(
            organization=request.user.organization
        ).select_related("patient", "uploaded_by")

        doc_status = request.query_params.get("status")
        if doc_status:
            documents = documents.filter(status=doc_status)

        file_type = request.query_params.get("file_type")
        if file_type:
            documents = documents.filter(file_type=file_type)

        patient = request.query_params.get("patient")
        if patient:
            try:
                uuid.UUID(patient)
            except ValueError:
                return Response(
                    {"patient": "Must be a valid UUID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            documents = documents.filter(patient_id=patient)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(documents, request, view=self)
        serializer = DocumentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Documents"],
        summary="Upload a document (doctor+)",
        description="Max 10 MB; PDF, JPEG or PNG. The file is stored in S3 and extraction "
                    "runs in the background, so the document starts as `uploaded`; poll "
                    "`GET /api/documents/{id}/` or its `/extraction/` endpoint. "
                    "Limited to 10 uploads per minute per organization.",
        request={"multipart/form-data": DocumentUploadSerializer},
        responses={201: DocumentSerializer, 400: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = DocumentUploadSerializer(
            data=request.data,
            context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data["file"]
        patient = serializer.validated_data["patient"]

        # Determine file type
        file_type = "pdf" if file.content_type == "application/pdf" else "image"

        # Upload to S3
        file_key = upload_file_to_s3(
            file_obj=file,
            organization_slug=request.user.organization.slug,
            original_filename=file.name,
            content_type=file.content_type,
        )

        # Save document record
        document = Document.objects.create(
            organization=request.user.organization,
            patient=patient,
            uploaded_by=request.user,
            file_key=file_key,
            original_filename=file.name,
            file_type=file_type,
            status="uploaded",
        )
        log_action(
            request, AuditLog.DOCUMENT_UPLOAD, "document", document.id,
            metadata={"filename": file.name, "patient_id": str(patient.id)},
        )
        extract_document_task.delay(str(document.id))

        return Response(
            DocumentSerializer(document).data,
            status=status.HTTP_201_CREATED
        )


class DocumentDetailView(APIView):
    permission_classes = [IsNurse]

    def get_object(self, pk, request):
        try:
            return Document.objects.select_related("patient", "uploaded_by").get(
                pk=pk, organization=request.user.organization
            )
        except Document.DoesNotExist:
            return None

    @extend_schema(
        tags=["Documents"],
        summary="Retrieve a document with a 1-hour download URL (nurse+)",
        responses={200: DocumentSerializer, 404: OpenApiResponse(description="Document not found")},
    )
    def get(self, request, pk):
        document = self.get_object(pk, request)
        if not document:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = DocumentSerializer(document)
        log_action(request, AuditLog.DOCUMENT_VIEW, "document", document.id)
        return Response(serializer.data)