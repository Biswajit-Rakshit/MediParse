from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer

from common.pagination import StandardPagination
from common.permissions import IsAdmin
from common.schema import PAGE_PARAMS, paginated



class AuditLogListView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="audit_logs_list",
        tags=["Audit"],
        summary="Audit logs for your organization (admin)",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("action", str, description="e.g. login, patient.view, document.upload"),
            OpenApiParameter("user", str, description="Partial match on user email."),
        ],
        responses=paginated(AuditLogSerializer),
    )
    def get(self, request):
        logs = AuditLog.objects.filter(organization=request.user.organization)

        action = request.query_params.get("action")
        if action:
            logs = logs.filter(action=action)

        email = request.query_params.get("user")
        if email:
            logs = logs.filter(user_email__icontains=email)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(logs, request, view=self)
        return paginator.get_paginated_response(
            AuditLogSerializer(page, many=True).data
        )