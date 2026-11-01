from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import uuid

from common.pagination import StandardPagination
from apps.documents.models import Document
from apps.documents.serializers import DocumentUploadSerializer, DocumentSerializer
from common.permissions import IsDoctor, IsNurse, IsSameOrganization
from apps.extraction.tasks import extract_document_task
from common.s3 import upload_file_to_s3


class DocumentListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsDoctor()]
        return [IsNurse()]

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

        extract_document_task.delay(str(document.id))

        return Response(
            DocumentSerializer(document).data,
            status=status.HTTP_201_CREATED
        )


class DocumentDetailView(APIView):
    permission_classes = [IsNurse]

    def get_object(self, pk, request):
        try:
            document = Document.objects.select_related(
                "patient", "uploaded_by"
            ).get(pk=pk)
            self.check_object_permissions(request, document)
            return document
        except Document.DoesNotExist:
            return None

    def get(self, request, pk):
        document = self.get_object(pk, request)
        if not document:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = DocumentSerializer(document)
        return Response(serializer.data)