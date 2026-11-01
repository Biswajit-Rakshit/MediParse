import uuid
from django.db import models
from apps.accounts.models import Organization


class Patient(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="patients"
    )
    name = models.CharField(max_length=255)
    dob = models.DateField(null=True, blank=True)
    patient_id = models.CharField(max_length=100)  # hospital's own ID
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="unknown")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "patient_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.patient_id})"