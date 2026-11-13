from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User


@pytest.fixture(autouse=True)
def clear_cache():
    """Throttle counters live in the cache; reset them around every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def mock_celery_delay():
    """Uploads queue a Celery task; in tests that call is a harmless mock."""
    with patch("apps.documents.views.extract_document_task.delay") as mocked:
        yield mocked


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Apollo Hospitals", slug="apollo")


@pytest.fixture
def other_org(db):
    return Organization.objects.create(name="City Hospital", slug="city")


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(organization, role="viewer", password="Str0ng-pass-99"):
        counter["n"] += 1
        return User.objects.create_user(
            email=f"{role}{counter['n']}@example.com",
            password=password,
            role=role,
            organization=organization,
        )

    return _make


@pytest.fixture
def client_for():
    """Returns an API client authenticated as the given user."""
    def _client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _client


@pytest.fixture
def api_client():
    return APIClient()