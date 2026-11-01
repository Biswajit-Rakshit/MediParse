import uuid
from django.db import models
from apps.documents.models import Document


class ExtractedRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="extracted_record",
    )
    raw_response = models.JSONField(default=dict)
    patient_name = models.CharField(max_length=255, blank=True)
    dob = models.DateField(null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True)
    doctor_name = models.CharField(max_length=255, blank=True)
    diagnosis = models.JSONField(default=list)      # list of strings
    medications = models.JSONField(default=list)    # list of {name, dosage, frequency}
    lab_values = models.JSONField(default=list)     # list of {test, value, unit, reference_range}
    confidence_score = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Extraction for {self.document.original_filename}"