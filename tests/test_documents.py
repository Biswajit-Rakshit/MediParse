from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.documents.models import Document
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

URL = "/api/documents/"


@pytest.fixture(autouse=True)
def mock_s3():
    """No real S3 in tests. The fixture yields the upload mock for assertions."""
    with patch(
        "apps.documents.views.upload_file_to_s3",
        return_value="documents/apollo/abc/scan.pdf",
    ) as upload, patch(
        "apps.documents.serializers.generate_presigned_url",
        return_value="https://example.test/signed",
    ):
        yield upload


def make_patient(org, patient_id="P-1"):
    return Patient.objects.create(organization=org, patient_id=patient_id, name="Test")


def make_document(org, patient, status="uploaded", file_type="pdf", name="scan.pdf"):
    return Document.objects.create(
        organization=org,
        patient=patient,
        file_key=f"documents/{org.slug}/x/{name}",
        original_filename=name,
        file_type=file_type,
        status=status,
    )


def pdf_file(name="scan.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake", content_type="application/pdf")


def upload(client, patient, file):
    return client.post(
        URL, {"file": file, "patient": str(patient.id)}, format="multipart"
    )


#upload

def test_doctor_uploads_pdf(org, make_user, client_for, mock_s3, mock_celery_delay):
    doctor = make_user(org, "doctor")
    patient = make_patient(org)

    response = upload(client_for(doctor), patient, pdf_file())

    assert response.status_code == 201
    assert response.data["status"] == "uploaded"
    assert response.data["file_type"] == "pdf"
    assert response.data["download_url"] == "https://example.test/signed"

    doc = Document.objects.get()
    assert doc.organization == org
    assert doc.uploaded_by == doctor
    assert doc.file_key == "documents/apollo/abc/scan.pdf"
    assert mock_s3.call_args.kwargs["organization_slug"] == "apollo"
    mock_celery_delay.assert_called_once_with(str(doc.id))
    assert AuditLog.objects.filter(
        action=AuditLog.DOCUMENT_UPLOAD, resource_id=str(doc.id)
    ).exists()


def test_png_is_stored_as_image(org, make_user, client_for):
    patient = make_patient(org)
    png = SimpleUploadedFile("photo.png", b"\x89PNG fake", content_type="image/png")

    response = upload(client_for(make_user(org, "doctor")), patient, png)

    assert response.status_code == 201
    assert response.data["file_type"] == "image"


def test_wrong_file_type_rejected(org, make_user, client_for, mock_s3):
    patient = make_patient(org)
    txt = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")

    response = upload(client_for(make_user(org, "doctor")), patient, txt)

    assert response.status_code == 400
    assert "file" in response.data
    mock_s3.assert_not_called()
    assert Document.objects.count() == 0


def test_oversized_file_rejected(org, make_user, client_for, mock_s3):
    patient = make_patient(org)
    big = SimpleUploadedFile(
        "big.pdf", b"0" * (10 * 1024 * 1024 + 1), content_type="application/pdf"
    )

    response = upload(client_for(make_user(org, "doctor")), patient, big)

    assert response.status_code == 400
    assert "file" in response.data
    mock_s3.assert_not_called()


def test_missing_file_rejected(org, make_user, client_for):
    patient = make_patient(org)
    response = client_for(make_user(org, "doctor")).post(
        URL, {"patient": str(patient.id)}, format="multipart"
    )
    assert response.status_code == 400
    assert "file" in response.data


def test_cannot_upload_for_other_orgs_patient(
    org, other_org, make_user, client_for, mock_s3
):
    foreign_patient = make_patient(other_org)

    response = upload(client_for(make_user(org, "doctor")), foreign_patient, pdf_file())

    assert response.status_code == 400
    assert "patient" in response.data
    mock_s3.assert_not_called()
    assert Document.objects.count() == 0


@pytest.mark.parametrize("role", ["nurse", "viewer"])
def test_nurse_and_viewer_cannot_upload(role, org, make_user, client_for, mock_s3):
    patient = make_patient(org)

    response = upload(client_for(make_user(org, role)), patient, pdf_file())

    assert response.status_code == 403
    mock_s3.assert_not_called()
    assert Document.objects.count() == 0


def test_upload_requires_authentication(org, api_client):
    patient = make_patient(org)
    assert upload(api_client, patient, pdf_file()).status_code == 401


#list and retrieve

def test_list_is_org_scoped(org, other_org, make_user, client_for):
    mine = make_document(org, make_patient(org))
    make_document(other_org, make_patient(other_org))

    response = client_for(make_user(org, "nurse")).get(URL)

    assert response.status_code == 200
    assert [d["id"] for d in response.data["results"]] == [str(mine.id)]


def test_viewer_cannot_list_documents(org, make_user, client_for):
    assert client_for(make_user(org, "viewer")).get(URL).status_code == 403


def test_list_filters(org, make_user, client_for):
    patient_a = make_patient(org, "A")
    patient_b = make_patient(org, "B")
    make_document(org, patient_a, status="completed")
    make_document(org, patient_a, status="failed")
    make_document(org, patient_b, status="completed", file_type="image", name="x.png")
    client = client_for(make_user(org, "nurse"))

    assert client.get(URL, {"status": "completed"}).data["count"] == 2
    assert client.get(URL, {"file_type": "image"}).data["count"] == 1
    assert client.get(URL, {"patient": str(patient_a.id)}).data["count"] == 2


def test_invalid_patient_filter_is_400_not_500(org, make_user, client_for):
    response = client_for(make_user(org, "nurse")).get(URL, {"patient": "not-a-uuid"})
    assert response.status_code == 400


def test_retrieve_document_and_audit(org, make_user, client_for):
    doc = make_document(org, make_patient(org))
    nurse = make_user(org, "nurse")

    response = client_for(nurse).get(f"{URL}{doc.id}/")

    assert response.status_code == 200
    assert response.data["id"] == str(doc.id)
    assert AuditLog.objects.filter(
        action=AuditLog.DOCUMENT_VIEW, resource_id=str(doc.id), user=nurse
    ).exists()


def test_cannot_retrieve_other_orgs_document(org, other_org, make_user, client_for):
    foreign = make_document(other_org, make_patient(other_org))

    response = client_for(make_user(org, "admin")).get(f"{URL}{foreign.id}/")

    assert response.status_code == 404
    assert not AuditLog.objects.filter(action=AuditLog.DOCUMENT_VIEW).exists()