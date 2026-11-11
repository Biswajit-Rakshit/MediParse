from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from common.pagination import StandardPagination
from common.permissions import IsAdmin


class AuditLogListView(APIView):
    permission_classes = [IsAdmin]

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