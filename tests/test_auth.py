import pytest

from apps.accounts.models import Organization, User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
USERS_URL = "/api/auth/users/"
PASSWORD = "Str0ng-pass-99"


def register_payload(**overrides):
    payload = {
        "email": "owner@newhospital.com",
        "password": PASSWORD,
        "organization_name": "New Hospital",
        "organization_slug": "new-hospital",
    }
    payload.update(overrides)
    return payload


#registration

def test_register_creates_new_org_with_admin(api_client):
    response = api_client.post(REGISTER_URL, register_payload(), format="json")

    assert response.status_code == 201
    assert response.data["user"]["role"] == "admin"
    assert "access" in response.data["tokens"]
    user = User.objects.get(email="owner@newhospital.com")
    assert user.organization.slug == "new-hospital"


def test_register_ignores_client_supplied_role(api_client):
    response = api_client.post(
        REGISTER_URL, register_payload(role="viewer"), format="json"
    )
    assert response.status_code == 201
    assert response.data["user"]["role"] == "admin"


def test_register_cannot_join_existing_org(api_client, org):
    response = api_client.post(
        REGISTER_URL,
        register_payload(organization_slug=org.slug),
        format="json",
    )
    assert response.status_code == 400
    assert "organization_slug" in response.data
    assert not User.objects.filter(email="owner@newhospital.com").exists()


def test_register_lowercases_slug(api_client):
    api_client.post(
        REGISTER_URL, register_payload(organization_slug="MiXed-Case"), format="json"
    )
    assert Organization.objects.filter(slug="mixed-case").exists()


def test_register_rejects_weak_password(api_client):
    response = api_client.post(
        REGISTER_URL, register_payload(password="12345678"), format="json"
    )
    assert response.status_code == 400
    assert "password" in response.data
    assert not Organization.objects.filter(slug="new-hospital").exists()


def test_register_writes_audit_entry(api_client):
    api_client.post(REGISTER_URL, register_payload(), format="json")
    assert AuditLog.objects.filter(action=AuditLog.REGISTER).exists()


#login

def test_login_success_returns_tokens_and_logs(api_client, org, make_user):
    user = make_user(org, "doctor", PASSWORD)
    response = api_client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == 200
    assert "access" in response.data["tokens"]
    assert "refresh" in response.data["tokens"]
    assert AuditLog.objects.filter(action=AuditLog.LOGIN, user=user).exists()


def test_login_wrong_password_fails_and_logs(api_client, org, make_user):
    user = make_user(org, "doctor", PASSWORD)
    response = api_client.post(
        LOGIN_URL, {"email": user.email, "password": "wrong-password"}, format="json"
    )

    assert response.status_code == 400
    entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
    assert entry.metadata["email"] == user.email
    assert not AuditLog.objects.filter(action=AuditLog.LOGIN).exists()


def test_inactive_user_cannot_log_in(api_client, org, make_user):
    user = make_user(org, "nurse", PASSWORD)
    user.is_active = False
    user.save()
    response = api_client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 400


def test_me_requires_authentication(api_client):
    assert api_client.get("/api/auth/me/").status_code == 401


def test_me_returns_current_user(org, make_user, client_for):
    user = make_user(org, "nurse")
    response = client_for(user).get("/api/auth/me/")
    assert response.status_code == 200
    assert response.data["email"] == user.email


#admin user management

def test_admin_adds_user_to_own_org_only(org, other_org, make_user, client_for):
    admin = make_user(org, "admin")
    response = client_for(admin).post(
        USERS_URL,
        {
            "email": "new.nurse@example.com",
            "password": PASSWORD,
            "role": "nurse",
            "organization": str(other_org.id),  # must be ignored
        },
        format="json",
    )

    assert response.status_code == 201
    created = User.objects.get(email="new.nurse@example.com")
    assert created.organization == org
    assert created.role == "nurse"
    assert AuditLog.objects.filter(action=AuditLog.USER_CREATE).exists()


@pytest.mark.parametrize("role", ["doctor", "nurse", "viewer"])
def test_non_admins_cannot_manage_users(role, org, make_user, client_for):
    client = client_for(make_user(org, role))
    assert client.get(USERS_URL).status_code == 403
    assert client.post(
        USERS_URL,
        {"email": "x@example.com", "password": PASSWORD, "role": "viewer"},
        format="json",
    ).status_code == 403


def test_admin_user_list_is_org_scoped(org, other_org, make_user, client_for):
    admin = make_user(org, "admin")
    make_user(org, "nurse")
    outsider = make_user(other_org, "nurse")

    response = client_for(admin).get(USERS_URL)

    assert response.status_code == 200
    emails = [u["email"] for u in response.data["results"]]
    assert outsider.email not in emails
    assert response.data["count"] == 2