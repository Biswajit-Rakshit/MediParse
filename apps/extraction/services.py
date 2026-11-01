from datetime import datetime
from typing import List, Optional

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel

from apps.extraction.models import ExtractedRecord
from common.s3 import download_file_from_s3


class Medication(BaseModel):
    name: str
    dosage: Optional[str]
    frequency: Optional[str]


class LabValue(BaseModel):
    test: str
    value: str
    unit: Optional[str]
    reference_range: Optional[str]


class ExtractionResult(BaseModel):
    patient_name: Optional[str]
    dob: Optional[str]          # YYYY-MM-DD
    visit_date: Optional[str]   # YYYY-MM-DD
    doctor_name: Optional[str]
    diagnosis: List[str]
    medications: List[Medication]
    lab_values: List[LabValue]
    confidence_score: float     # 0.0 to 1.0, model's own estimate


SYSTEM_INSTRUCTION = """You extract structured data from medical documents.
Rules:
- Extract only what is explicitly present in the document. Never guess or infer.
- Use null for any single value that is missing or unreadable, and [] for empty lists.
- Write all dates as YYYY-MM-DD.
- Keep medication dosage and frequency exactly as written.
- confidence_score is your overall confidence (0.0 to 1.0) that the extraction
  is complete and accurate. Lower it for blurry, partial or ambiguous documents."""

MIME_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


def _get_mime_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return MIME_TYPES.get(ext, "application/pdf")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def run_extraction(document):
    """Downloads the document from S3, sends it to Gemini, saves the result."""
    file_bytes = download_file_from_s3(document.file_key)

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=_get_mime_type(document.original_filename),
            ),
            "Extract the structured data from this medical document.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
        ),
    )

    result = response.parsed
    if result is None:
        raise ValueError("Gemini returned no parseable result.")

    record, _ = ExtractedRecord.objects.update_or_create(
        document=document,
        defaults={
            "raw_response": result.model_dump(),
            "patient_name": result.patient_name or "",
            "dob": _parse_date(result.dob),
            "visit_date": _parse_date(result.visit_date),
            "doctor_name": result.doctor_name or "",
            "diagnosis": result.diagnosis,
            "medications": [m.model_dump() for m in result.medications],
            "lab_values": [l.model_dump() for l in result.lab_values],
            "confidence_score": result.confidence_score,
            "error_message": "",
        },
    )
    return record