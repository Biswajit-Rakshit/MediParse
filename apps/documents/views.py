from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.documents.models import Document
from apps.documents.serializers import DocumentUploadSerializer, DocumentSerializer
from common.permissions import IsDoctor, IsNurse, IsSameOrganization
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
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

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