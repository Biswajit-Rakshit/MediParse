from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.patients.models import Patient
from common.throttles import OrganizationRateThrottle, UploadRateThrottle

pytestmark = pytest.mark.django_db

PATIENTS = "/api/patients/"
DOCUMENTS = "/api/documents/"
LOGIN = "/api/auth/login/"


@pytest.fixture
def tight_org_limits(monkeypatch):
    """Shrink the limits so tests need only a few requests."""
    monkeypatch.setitem(OrganizationRateThrottle.tier_rates, "free", "3/min")
    monkeypatch.setitem(OrganizationRateThrottle.tier_rates, "pro", "6/min")


@pytest.fixture
def mock_s3():
    with patch(
        "apps.documents.views.upload_file_to_s3", return_value="documents/x/y/scan.pdf"
    ), patch(
        "apps.documents.serializers.generate_presigned_url",
        return_value="https://example.test/signed",
    ):
        yield


def hit(client, times, url=PATIENTS):
    return [client.get(url).status_code for _ in range(times)]


# per-organization limit

def test_free_org_is_throttled_with_retry_after(
    tight_org_limits, org, make_user, client_for
):
    client = client_for(make_user(org, "nurse"))

    assert hit(client, 3) == [200, 200, 200]
    response = client.get(PATIENTS)

    assert response.status_code == 429
    assert "Retry-After" in response


def test_limit_is_shared_by_all_users_of_an_org(
    tight_org_limits, org, make_user, client_for
):
    first = client_for(make_user(org, "nurse"))
    second = client_for(make_user(org, "doctor"))

    hit(first, 2)
    hit(second, 1)

    assert first.get(PATIENTS).status_code == 429
    assert second.get(PATIENTS).status_code == 429


def test_orgs_have_separate_counters(
    tight_org_limits, org, other_org, make_user, client_for
):
    busy = client_for(make_user(org, "nurse"))
    quiet = client_for(make_user(other_org, "nurse"))

    hit(busy, 4)

    assert busy.get(PATIENTS).status_code == 429
    assert quiet.get(PATIENTS).status_code == 200


def test_pro_tier_gets_higher_limit(tight_org_limits, org, make_user, client_for):
    org.plan_tier = "pro"
    org.save()
    client = client_for(make_user(org, "nurse"))

    assert hit(client, 6) == [200] * 6
    assert client.get(PATIENTS).status_code == 429


def test_unknown_tier_falls_back_to_free(tight_org_limits, org, make_user, client_for):
    org.plan_tier = "mystery"
    org.save()
    client = client_for(make_user(org, "nurse"))

    assert hit(client, 3) == [200, 200, 200]
    assert client.get(PATIENTS).status_code == 429


# upload limit

def test_upload_limit_is_stricter_and_separate(
    monkeypatch, org, make_user, client_for, mock_s3
):
    monkeypatch.setitem(UploadRateThrottle.tier_rates, "free", "2/min")
    doctor = make_user(org, "doctor")
    patient = Patient.objects.create(organization=org, patient_id="P-1", name="T")
    client = client_for(doctor)

    def upload():
        file = SimpleUploadedFile("scan.pdf", b"%PDF-fake", content_type="application/pdf")
        return client.post(
            DOCUMENTS, {"file": file, "patient": str(patient.id)}, format="multipart"
        )

    assert upload().status_code == 201
    assert upload().status_code == 201
    assert upload().status_code == 429
    # reading is unaffected by the upload limit
    assert client.get(DOCUMENTS).status_code == 200


# anonymous limit

def test_anonymous_limit_slows_login_guessing(api_client):
    payload = {"email": "nobody@example.com", "password": "wrong"}

    codes = [api_client.post(LOGIN, payload, format="json").status_code for _ in range(20)]
    assert set(codes) == {400}

    assert api_client.post(LOGIN, payload, format="json").status_code == 429


def test_anonymous_limit_is_per_ip(api_client):
    payload = {"email": "nobody@example.com", "password": "wrong"}
    for _ in range(21):
        api_client.post(LOGIN, payload, format="json")

    other_ip = api_client.post(LOGIN, payload, format="json", REMOTE_ADDR="10.9.9.9")
    assert other_ip.status_code == 400  # not throttled