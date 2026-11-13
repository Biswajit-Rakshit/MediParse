from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.conf import settings

from apps.audit.models import AuditLog
from apps.documents.models import Document
from apps.extraction.models import ExtractedRecord
from apps.extraction.services import (
    ExtractionResult,
    LabValue,
    Medication,
    _get_mime_type,
    run_extraction,
)
from apps.extraction.tasks import extract_document_task
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


def make_result(**overrides):
    data = dict(
        patient_name="Rajesh Kumar",
        dob="1985-06-15",
        visit_date="2026-10-01",
        doctor_name="Dr. Mehta",
        diagnosis=["Hypertension"],
        medications=[Medication(name="Amlodipine", dosage="5 mg", frequency="once daily")],
        lab_values=[
            LabValue(test="HbA1c", value="6.1", unit="%", reference_range="4-5.6")
        ],
        confidence_score=0.92,
    )
    data.update(overrides)
    return ExtractionResult(**data)


@pytest.fixture
def doc(org):
    patient = Patient.objects.create(
        organization=org, patient_id="P-1", name="Rajesh Kumar"
    )
    return Document.objects.create(
        organization=org,
        patient=patient,
        file_key="documents/apollo/x/scan.pdf",
        original_filename="scan.pdf",
        file_type="pdf",
        status="processing",
    )


@pytest.fixture
def mock_gemini():
    """Replaces S3 download and the Gemini client; no network is touched."""
    with patch(
        "apps.extraction.services.download_file_from_s3", return_value=b"%PDF-fake"
    ) as download, patch("apps.extraction.services.genai.Client") as client_cls:
        generate = client_cls.return_value.models.generate_content
        generate.return_value = SimpleNamespace(parsed=make_result())
        yield SimpleNamespace(download=download, generate=generate)


#service

def test_mime_type_detection():
    assert _get_mime_type("scan.PDF") == "application/pdf"
    assert _get_mime_type("photo.jpeg") == "image/jpeg"
    assert _get_mime_type("photo.png") == "image/png"


def test_run_extraction_saves_structured_record(doc, mock_gemini):
    record = run_extraction(doc)

    assert record.patient_name == "Rajesh Kumar"
    assert record.dob == date(1985, 6, 15)
    assert record.visit_date == date(2026, 10, 1)
    assert record.doctor_name == "Dr. Mehta"
    assert record.diagnosis == ["Hypertension"]
    assert record.medications == [
        {"name": "Amlodipine", "dosage": "5 mg", "frequency": "once daily"}
    ]
    assert record.lab_values[0]["test"] == "HbA1c"
    assert record.confidence_score == 0.92
    mock_gemini.download.assert_called_once_with(doc.file_key)


def test_run_extraction_sends_file_and_json_config(doc, mock_gemini):
    run_extraction(doc)

    kwargs = mock_gemini.generate.call_args.kwargs
    assert kwargs["model"] == settings.GEMINI_MODEL
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["contents"][0].inline_data.mime_type == "application/pdf"


def test_malformed_dates_become_none(doc, mock_gemini):
    mock_gemini.generate.return_value = SimpleNamespace(
        parsed=make_result(dob="15/06/1985", visit_date=None)
    )

    record = run_extraction(doc)

    assert record.dob is None
    assert record.visit_date is None
    assert record.patient_name == "Rajesh Kumar"  # the rest survives


def test_rerunning_extraction_updates_instead_of_duplicating(doc, mock_gemini):
    run_extraction(doc)
    mock_gemini.generate.return_value = SimpleNamespace(
        parsed=make_result(doctor_name="Dr. Rao")
    )
    run_extraction(doc)

    assert ExtractedRecord.objects.filter(document=doc).count() == 1
    assert ExtractedRecord.objects.get(document=doc).doctor_name == "Dr. Rao"


def test_successful_rerun_clears_old_error(doc, mock_gemini):
    ExtractedRecord.objects.create(document=doc, error_message="old failure")
    record = run_extraction(doc)
    assert record.error_message == ""


def test_unparseable_response_raises(doc, mock_gemini):
    mock_gemini.generate.return_value = SimpleNamespace(parsed=None)
    with pytest.raises(ValueError):
        run_extraction(doc)
    assert not ExtractedRecord.objects.filter(document=doc).exists()


#celery task-calling a task object directly runs it in-process, no worker or Redis needed.

def test_task_success_marks_completed(doc):
    with patch("apps.extraction.tasks.run_extraction") as run:
        extract_document_task(str(doc.id))

    run.assert_called_once()
    doc.refresh_from_db()
    assert doc.status == "completed"


def test_task_marks_processing_before_extracting(doc):
    seen = {}

    def fake_run(document):
        seen["status"] = Document.objects.get(pk=document.pk).status

    doc.status = "uploaded"
    doc.save()
    with patch("apps.extraction.tasks.run_extraction", side_effect=fake_run):
        extract_document_task(str(doc.id))

    assert seen["status"] == "processing"


def test_task_error_is_retried_not_failed(doc):
    # Called directly, Celery re-raises the original error from self.retry().
    # The document must stay "processing" because a retry is still pending.
    with patch("apps.extraction.tasks.run_extraction", side_effect=RuntimeError("rate limited")):
        with pytest.raises(RuntimeError):
            extract_document_task(str(doc.id))

    doc.refresh_from_db()
    assert doc.status == "processing"


def test_task_marks_failed_when_retries_exhausted(doc, monkeypatch):
    monkeypatch.setattr(extract_document_task, "max_retries", 0)

    with patch("apps.extraction.tasks.run_extraction", side_effect=RuntimeError("boom")):
        extract_document_task(str(doc.id))

    doc.refresh_from_db()
    assert doc.status == "failed"
    assert ExtractedRecord.objects.get(document=doc).error_message == "boom"


def test_task_truncates_long_error_messages(doc, monkeypatch):
    monkeypatch.setattr(extract_document_task, "max_retries", 0)

    with patch("apps.extraction.tasks.run_extraction", side_effect=RuntimeError("x" * 5000)):
        extract_document_task(str(doc.id))

    assert len(ExtractedRecord.objects.get(document=doc).error_message) == 1000


def test_task_ignores_deleted_document():
    assert extract_document_task(str(uuid4())) is None


#endpoints

def make_record(document, **overrides):
    fields = dict(
        patient_name="Rajesh Kumar",
        doctor_name="Dr. Mehta",
        diagnosis=["Hypertension"],
        confidence_score=0.9,
    )
    fields.update(overrides)
    return ExtractedRecord.objects.create(document=document, **fields)


def test_extraction_not_ready_returns_null(doc, org, make_user, client_for):
    response = client_for(make_user(org, "nurse")).get(
        f"/api/documents/{doc.id}/extraction/"
    )
    assert response.status_code == 200
    assert response.data["extraction"] is None
    assert response.data["status"] == "processing"


def test_extraction_returns_data_and_audits(doc, org, make_user, client_for):
    make_record(doc)
    nurse = make_user(org, "nurse")

    response = client_for(nurse).get(f"/api/documents/{doc.id}/extraction/")

    assert response.status_code == 200
    assert response.data["patient_name"] == "Rajesh Kumar"
    assert response.data["diagnosis"] == ["Hypertension"]
    assert "raw_response" not in response.data
    assert AuditLog.objects.filter(
        action=AuditLog.EXTRACTION_VIEW, resource_id=str(doc.id), user=nurse
    ).exists()


def test_failed_extraction_exposes_error(doc, org, make_user, client_for):
    doc.status = "failed"
    doc.save()
    make_record(doc, patient_name="", diagnosis=[], confidence_score=None,
                error_message="boom")

    response = client_for(make_user(org, "nurse")).get(
        f"/api/documents/{doc.id}/extraction/"
    )

    assert response.data["document_status"] == "failed"
    assert response.data["error_message"] == "boom"


def test_extraction_of_other_orgs_document_is_404(doc, other_org, make_user, client_for):
    make_record(doc)
    outsider = make_user(other_org, "admin")

    response = client_for(outsider).get(f"/api/documents/{doc.id}/extraction/")

    assert response.status_code == 404
    assert not AuditLog.objects.filter(action=AuditLog.EXTRACTION_VIEW).exists()


def test_viewer_cannot_read_extractions(doc, org, make_user, client_for):
    viewer = client_for(make_user(org, "viewer"))
    assert viewer.get(f"/api/documents/{doc.id}/extraction/").status_code == 403
    assert viewer.get("/api/extractions/").status_code == 403


def test_extraction_list_is_org_scoped(doc, org, other_org, make_user, client_for):
    make_record(doc)
    foreign_patient = Patient.objects.create(organization=other_org, patient_id="F", name="F")
    foreign_doc = Document.objects.create(
        organization=other_org, patient=foreign_patient, file_key="k",
        original_filename="f.pdf", file_type="pdf",
    )
    make_record(foreign_doc, patient_name="Outsider")

    response = client_for(make_user(org, "nurse")).get("/api/extractions/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["patient_name"] == "Rajesh Kumar"


def test_extraction_list_search_and_confidence_filter(doc, org, make_user, client_for):
    make_record(doc, patient_name="Rajesh Kumar", confidence_score=0.95)
    other_doc = Document.objects.create(
        organization=org, patient=doc.patient, file_key="k2",
        original_filename="b.pdf", file_type="pdf",
    )
    make_record(other_doc, patient_name="Priya Sharma", doctor_name="Dr. Rao",
                confidence_score=0.4)
    client = client_for(make_user(org, "nurse"))

    by_name = client.get("/api/extractions/", {"search": "priya"})
    assert [r["patient_name"] for r in by_name.data["results"]] == ["Priya Sharma"]

    by_doctor = client.get("/api/extractions/", {"search": "rao"})
    assert by_doctor.data["count"] == 1

    confident = client.get("/api/extractions/", {"min_confidence": "0.9"})
    assert [r["patient_name"] for r in confident.data["results"]] == ["Rajesh Kumar"]


def test_invalid_min_confidence_is_400(org, make_user, client_for):
    response = client_for(make_user(org, "nurse")).get(
        "/api/extractions/", {"min_confidence": "high"}
    )
    assert response.status_code == 400