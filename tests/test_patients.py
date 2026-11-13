import pytest

from apps.audit.models import AuditLog
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

URL = "/api/patients/"


def make_patient(org, patient_id="P-1", name="Test Patient", gender="unknown"):
    return Patient.objects.create(
        organization=org, patient_id=patient_id, name=name, gender=gender
    )


#permissions

def test_unauthenticated_is_rejected(api_client):
    assert api_client.get(URL).status_code == 401


@pytest.mark.parametrize("role", ["admin", "doctor"])
def test_doctor_and_admin_can_create(role, org, make_user, client_for):
    client = client_for(make_user(org, role))
    response = client.post(
        URL, {"name": "Rajesh Kumar", "patient_id": "APL-001", "gender": "male"},
        format="json",
    )
    assert response.status_code == 201
    assert Patient.objects.get(patient_id="APL-001").organization == org


@pytest.mark.parametrize("role", ["nurse", "viewer"])
def test_nurse_and_viewer_cannot_create(role, org, make_user, client_for):
    client = client_for(make_user(org, role))
    response = client.post(
        URL, {"name": "X", "patient_id": "X-1"}, format="json"
    )
    assert response.status_code == 403
    assert Patient.objects.count() == 0


def test_nurse_can_read(org, make_user, client_for):
    make_patient(org)
    response = client_for(make_user(org, "nurse")).get(URL)
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_viewer_cannot_read_patients(org, make_user, client_for):
    # Current behaviour: patient endpoints require nurse or above.
    make_patient(org)
    assert client_for(make_user(org, "viewer")).get(URL).status_code == 403


def test_client_cannot_set_organization(org, other_org, make_user, client_for):
    client = client_for(make_user(org, "doctor"))
    client.post(
        URL,
        {"name": "X", "patient_id": "X-1", "organization": str(other_org.id)},
        format="json",
    )
    assert Patient.objects.get(patient_id="X-1").organization == org


#validation

def test_duplicate_patient_id_in_same_org_rejected(org, make_user, client_for):
    make_patient(org, patient_id="DUP-1")
    response = client_for(make_user(org, "doctor")).post(
        URL, {"name": "Other", "patient_id": "DUP-1"}, format="json"
    )
    assert response.status_code == 400
    assert "patient_id" in response.data


def test_same_patient_id_allowed_in_different_org(org, other_org, make_user, client_for):
    make_patient(other_org, patient_id="SHARED-1")
    response = client_for(make_user(org, "doctor")).post(
        URL, {"name": "Mine", "patient_id": "SHARED-1"}, format="json"
    )
    assert response.status_code == 201


#multi-tenancy

def test_list_excludes_other_orgs_patients(org, other_org, make_user, client_for):
    make_patient(org, patient_id="MINE")
    make_patient(other_org, patient_id="THEIRS")
    response = client_for(make_user(org, "nurse")).get(URL)
    ids = [p["patient_id"] for p in response.data["results"]]
    assert ids == ["MINE"]


def test_cannot_retrieve_other_orgs_patient(org, other_org, make_user, client_for):
    foreign = make_patient(other_org)
    response = client_for(make_user(org, "admin")).get(f"{URL}{foreign.id}/")
    assert response.status_code == 404


def test_cannot_update_other_orgs_patient(org, other_org, make_user, client_for):
    foreign = make_patient(other_org, name="Original")
    response = client_for(make_user(org, "admin")).patch(
        f"{URL}{foreign.id}/", {"name": "Hacked"}, format="json"
    )
    assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.name == "Original"


#update

def test_doctor_can_update_patient(org, make_user, client_for):
    patient = make_patient(org)
    response = client_for(make_user(org, "doctor")).patch(
        f"{URL}{patient.id}/", {"gender": "female"}, format="json"
    )
    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.gender == "female"


def test_nurse_cannot_update_patient(org, make_user, client_for):
    patient = make_patient(org)
    response = client_for(make_user(org, "nurse")).patch(
        f"{URL}{patient.id}/", {"gender": "female"}, format="json"
    )
    assert response.status_code == 403


#pagination and filters

def test_pagination_shape_and_page_size(org, make_user, client_for):
    for i in range(25):
        make_patient(org, patient_id=f"P-{i}")
    client = client_for(make_user(org, "nurse"))

    first = client.get(URL)
    assert first.data["count"] == 25
    assert len(first.data["results"]) == 20
    assert first.data["next"] is not None

    small = client.get(URL, {"page_size": 5})
    assert len(small.data["results"]) == 5


def test_search_and_gender_filters(org, make_user, client_for):
    make_patient(org, patient_id="A-1", name="Rajesh Kumar", gender="male")
    make_patient(org, patient_id="A-2", name="Priya Sharma", gender="female")
    client = client_for(make_user(org, "nurse"))

    by_name = client.get(URL, {"search": "priya"})
    assert [p["patient_id"] for p in by_name.data["results"]] == ["A-2"]

    by_gender = client.get(URL, {"gender": "male"})
    assert [p["patient_id"] for p in by_gender.data["results"]] == ["A-1"]


#audit

def test_create_and_view_are_audited(org, make_user, client_for):
    doctor = make_user(org, "doctor")
    client = client_for(doctor)
    created = client.post(URL, {"name": "A", "patient_id": "AUD-1"}, format="json")
    patient_id = created.data["id"]
    client.get(f"{URL}{patient_id}/")

    assert AuditLog.objects.filter(
        action=AuditLog.PATIENT_CREATE, resource_id=patient_id, user=doctor
    ).exists()
    assert AuditLog.objects.filter(
        action=AuditLog.PATIENT_VIEW, resource_id=patient_id, user=doctor
    ).exists()