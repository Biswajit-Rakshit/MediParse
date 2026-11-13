import pytest
from django.core.management import call_command


def test_schema_generates_without_warnings(tmp_path):
    # --fail-on-warn turns any undocumented or ambiguous view into a failure
    call_command(
        "spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yml")
    )


def test_schema_documents_every_endpoint(api_client):
    response = api_client.get("/api/schema/", {"format": "json"})
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in [
        "/api/auth/register/", "/api/auth/login/", "/api/auth/users/",
        "/api/patients/", "/api/documents/", "/api/documents/{id}/extraction/",
        "/api/extractions/", "/api/audit/logs/",
    ]:
        assert path in paths


def test_upload_is_documented_as_multipart(api_client):
    paths = api_client.get("/api/schema/", {"format": "json"}).json()["paths"]
    body = paths["/api/documents/"]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in body