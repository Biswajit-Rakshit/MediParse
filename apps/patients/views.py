from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q

from apps.patients.models import Patient
from apps.patients.serializers import PatientSerializer
from apps.audit.models import AuditLog
from apps.audit.utils import log_action

from common.pagination import StandardPagination
from common.permissions import IsDoctor, IsNurse, IsSameOrganization


class PatientListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsDoctor()]
        return [IsNurse()]

    def get(self, request):
        patients = Patient.objects.filter(organization=request.user.organization)

        search = request.query_params.get("search")
        if search:
            patients = patients.filter(
                Q(name__icontains=search) | Q(patient_id__icontains=search)
            )

        gender = request.query_params.get("gender")
        if gender:
            patients = patients.filter(gender=gender)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(patients, request, view=self)
        serializer = PatientSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = PatientSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            patient = serializer.save()
            log_action(request, AuditLog.PATIENT_CREATE, "patient", patient.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientDetailView(APIView):

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT"]:
            return [IsDoctor()]
        return [IsNurse()]

    def get_object(self, pk, request):
        try:
            return Patient.objects.get(pk=pk, organization=request.user.organization)
        except Patient.DoesNotExist:
            return None

    def get(self, request, pk):
        patient = self.get_object(pk, request)
        if not patient:
            return Response(
                {"detail": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        log_action(request, AuditLog.PATIENT_VIEW, "patient", patient.id)
        serializer = PatientSerializer(patient, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, pk):
        patient = self.get_object(pk, request)
        if not patient:
            return Response(
                {"detail": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = PatientSerializer(
            patient, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            log_action(
                request, AuditLog.PATIENT_UPDATE, "patient", patient.id,
                metadata={"fields": list(request.data.keys())},
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)