import uuid
from django.db import models
from apps.accounts.models import Organization, User


class AuditLog(models.Model):
    # action names used across the project
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    REGISTER = "register"
    PATIENT_CREATE = "patient.create"
    PATIENT_VIEW = "patient.view"
    PATIENT_UPDATE = "patient.update"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_VIEW = "document.view"
    EXTRACTION_VIEW = "extraction.view"
    USER_CREATE = "user.create"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    user_email = models.CharField(max_length=255, blank=True)  # snapshot
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=50, db_index=True)
    resource_type = models.CharField(max_length=50, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Audit logs are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit logs cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.user_email} {self.action}"