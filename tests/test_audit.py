from unittest.mock import patch

import pytest

from apps.audit.models import AuditLog
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

URL = "/api/audit/logs/"


def make_log(org, user=None, action="patient.view", email="x@example.com", **kwargs):
    return AuditLog.objects.create(
        organization=org, user=user, user_email=email, action=action, **kwargs
    )


#access control

def test_audit_logs_require_authentication(api_client):
    assert api_client.get(URL).status_code == 401


@pytest.mark.parametrize("role", ["doctor", "nurse", "viewer"])
def test_only_admin_can_read_audit_logs(role, org, make_user, client_for):
    assert client_for(make_user(org, role)).get(URL).status_code == 403


def test_admin_can_read_audit_logs(org, make_user, client_for):
    make_log(org)
    response = client_for(make_user(org, "admin")).get(URL)
    assert response.status_code == 200
    assert response.data["count"] == 1


#scoping, filters, ordering

def test_logs_are_org_scoped(org, other_org, make_user, client_for):
    make_log(org, email="mine@example.com")
    make_log(other_org, email="theirs@example.com")

    response = client_for(make_user(org, "admin")).get(URL)

    emails = [entry["user_email"] for entry in response.data["results"]]
    assert emails == ["mine@example.com"]


def test_filter_by_action_and_user(org, make_user, client_for):
    make_log(org, action="login", email="alice@example.com")
    make_log(org, action="patient.view", email="alice@example.com")
    make_log(org, action="patient.view", email="bob@example.com")
    client = client_for(make_user(org, "admin"))

    assert client.get(URL, {"action": "login"}).data["count"] == 1
    assert client.get(URL, {"action": "patient.view"}).data["count"] == 2
    assert client.get(URL, {"user": "bob"}).data["count"] == 1
    both = client.get(URL, {"action": "patient.view", "user": "alice"})
    assert both.data["count"] == 1


def test_logs_are_newest_first_and_paginated(org, make_user, client_for):
    for i in range(25):
        make_log(org, action=f"event.{i}")
    client = client_for(make_user(org, "admin"))

    first = client.get(URL)
    assert first.data["count"] == 25
    assert len(first.data["results"]) == 20
    assert first.data["results"][0]["action"] == "event.24"


#append-only guarantees

def test_audit_log_cannot_be_modified(org):
    entry = make_log(org)
    entry.action = "tampered"
    with pytest.raises(PermissionError):
        entry.save()


def test_audit_log_cannot_be_deleted(org):
    entry = make_log(org)
    with pytest.raises(PermissionError):
        entry.delete()
    assert AuditLog.objects.filter(pk=entry.pk).exists()


def test_history_survives_user_deletion(org, make_user):
    user = make_user(org, "doctor")
    entry = make_log(org, user=user, email=user.email)

    user.delete()

    entry.refresh_from_db()
    assert entry.user is None
    assert entry.user_email == user.email  # the snapshot keeps who it was


#what gets recorded

def test_ip_is_taken_from_forwarded_header(api_client):
    api_client.post(
        "/api/auth/login/",
        {"email": "a@example.com", "password": "wrong"},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1",
    )
    assert AuditLog.objects.get(action=AuditLog.LOGIN_FAILED).ip_address == "203.0.113.5"


def test_ip_falls_back_to_remote_addr(api_client):
    api_client.post(
        "/api/auth/login/",
        {"email": "a@example.com", "password": "wrong"},
        format="json",
        REMOTE_ADDR="198.51.100.7",
    )
    assert AuditLog.objects.get(action=AuditLog.LOGIN_FAILED).ip_address == "198.51.100.7"


def test_patient_update_logs_field_names_not_values(org, make_user, client_for):
    patient = Patient.objects.create(organization=org, patient_id="P-1", name="Old Name")
    client = client_for(make_user(org, "doctor"))

    client.patch(f"/api/patients/{patient.id}/", {"name": "Secret New Name"}, format="json")

    entry = AuditLog.objects.get(action=AuditLog.PATIENT_UPDATE)
    assert entry.metadata == {"fields": ["name"]}
    assert "Secret New Name" not in str(entry.metadata)
    assert entry.resource_id == str(patient.id)