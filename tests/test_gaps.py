from unittest.mock import patch

import pytest
from django.db import IntegrityError

from apps.accounts.models import Organization, User
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng-pass-99"


# user manager

def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password=PASSWORD)


def test_create_superuser_sets_staff_flags():
    user = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
    assert user.is_staff and user.is_superuser


# registration race

def test_register_handles_slug_race_cleanly(api_client):
    # Simulates two requests passing the exists() check, then colliding in the DB.
    with patch.object(Organization.objects, "create", side_effect=IntegrityError):
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "a@example.com",
                "password": PASSWORD,
                "organization_name": "Race Hospital",
                "organization_slug": "race",
            },
            format="json",
        )
    assert response.status_code == 400
    assert not User.objects.filter(email="a@example.com").exists()


# admin user creation validation

def test_admin_create_user_rejects_weak_password(org, make_user, client_for):
    response = client_for(make_user(org, "admin")).post(
        "/api/auth/users/",
        {"email": "new@example.com", "password": "12345678", "role": "nurse"},
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.data


def test_admin_create_user_rejects_duplicate_email(org, make_user, client_for):
    existing = make_user(org, "nurse")
    response = client_for(make_user(org, "admin")).post(
        "/api/auth/users/",
        {"email": existing.email, "password": PASSWORD, "role": "nurse"},
        format="json",
    )
    assert response.status_code == 400
    assert "email" in response.data


def test_admin_create_user_rejects_unknown_role(org, make_user, client_for):
    response = client_for(make_user(org, "admin")).post(
        "/api/auth/users/",
        {"email": "new@example.com", "password": PASSWORD, "role": "superhero"},
        format="json",
    )
    assert response.status_code == 400
    assert "role" in response.data


# patient update validation

def test_patch_with_own_patient_id_is_allowed(org, make_user, client_for):
    patient = Patient.objects.create(organization=org, patient_id="P-1", name="Old")
    response = client_for(make_user(org, "doctor")).patch(
        f"/api/patients/{patient.id}/",
        {"patient_id": "P-1", "name": "New"},
        format="json",
    )
    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.name == "New"


def test_patch_cannot_take_another_patients_id(org, make_user, client_for):
    Patient.objects.create(organization=org, patient_id="P-1", name="First")
    second = Patient.objects.create(organization=org, patient_id="P-2", name="Second")
    response = client_for(make_user(org, "doctor")).patch(
        f"/api/patients/{second.id}/", {"patient_id": "P-1"}, format="json"
    )
    assert response.status_code == 400
    assert "patient_id" in response.data


def test_patch_with_invalid_value_is_400(org, make_user, client_for):
    patient = Patient.objects.create(organization=org, patient_id="P-1", name="X")
    response = client_for(make_user(org, "doctor")).patch(
        f"/api/patients/{patient.id}/", {"gender": "robot"}, format="json"
    )
    assert response.status_code == 400
    assert "gender" in response.data