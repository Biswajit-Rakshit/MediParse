from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.documents.models import Document
from apps.extraction.models import ExtractedRecord
from apps.extraction.serializers import ExtractedRecordSerializer
from apps.audit.models import AuditLog
from apps.audit.utils import log_action

from common.schema import PAGE_PARAMS, paginated
from common.pagination import StandardPagination
from common.permissions import IsNurse


class DocumentExtractionView(APIView):
    """Extraction result for a single document."""
    permission_classes = [IsNurse]

    @extend_schema(
        tags=["Extraction"],
        summary="Extraction result for one document (nurse+)",
        description="If extraction hasn't finished, returns `{document_id, status, extraction: null}` "
                    "instead of the full record, so clients can poll.",
        responses={200: ExtractedRecordSerializer, 404: OpenApiResponse(description="Document not found")},
    )
    def get(self, request, pk):
        try:
            document = Document.objects.get(
                pk=pk, organization=request.user.organization
            )
        except Document.DoesNotExist:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        log_action(request, AuditLog.EXTRACTION_VIEW, "document", document.id)
        record = ExtractedRecord.objects.filter(document=document).first()
        if record is None:
            # not extracted yet (uploaded / processing)
            return Response(
                {"document_id": str(document.id), "status": document.status, "extraction": None}
            )

        return Response(ExtractedRecordSerializer(record).data)


class ExtractedRecordListView(APIView):
    permission_classes = [IsNurse]

    @extend_schema(
        tags=["Extraction"],
        operation_id="extractions_list",
        summary="List extracted records in your organization (nurse+)",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("search", str, description="Matches patient or doctor name."),
            OpenApiParameter("min_confidence", float, description="0 to 1."),
        ],
        responses=paginated(ExtractedRecordSerializer),
    )
    def get(self, request):
        records = ExtractedRecord.objects.filter(
            document__organization=request.user.organization
        ).select_related("document")

        search = request.query_params.get("search")
        if search:
            records = records.filter(
                Q(patient_name__icontains=search) | Q(doctor_name__icontains=search)
            )

        min_conf = request.query_params.get("min_confidence")
        if min_conf:
            try:
                records = records.filter(confidence_score__gte=float(min_conf))
            except ValueError:
                return Response(
                    {"min_confidence": "Must be a number between 0 and 1."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(records, request, view=self)
        serializer = ExtractedRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)