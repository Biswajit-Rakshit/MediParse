from rest_framework import serializers
from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "user_email", "action", "resource_type",
            "resource_id", "ip_address", "metadata", "timestamp",
        ]
        read_only_fields = fields