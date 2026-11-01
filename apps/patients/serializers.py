from rest_framework import serializers
from apps.patients.models import Patient


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "id",
            "name",
            "dob",
            "patient_id",
            "gender",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_patient_id(self, value):
        """Ensure patient_id is unique within the organization."""
        request = self.context.get("request")
        org = request.user.organization
        qs = Patient.objects.filter(organization=org, patient_id=value)
        # Exclude current instance on update
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A patient with this ID already exists in your organization."
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["organization"] = request.user.organization
        return super().create(validated_data)