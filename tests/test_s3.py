import io
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from moto import mock_aws

from common import s3


@pytest.fixture
def bucket():
    """A fake in-memory S3 with our bucket in it. Exercises our real helper code."""
    with mock_aws():
        client = s3.get_s3_client()
        client.create_bucket(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": settings.AWS_S3_REGION},
        )
        yield client


def test_upload_stores_object_under_org_path_with_content_type(bucket):
    key = s3.upload_file_to_s3(
        io.BytesIO(b"hello"), "apollo", "scan.pdf", content_type="application/pdf"
    )

    assert key.startswith("documents/apollo/")
    assert key.endswith("/scan.pdf")
    head = bucket.head_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=key)
    assert head["ContentType"] == "application/pdf"


def test_each_upload_gets_a_unique_key(bucket):
    first = s3.upload_file_to_s3(io.BytesIO(b"a"), "apollo", "scan.pdf", content_type="application/pdf")
    second = s3.upload_file_to_s3(io.BytesIO(b"b"), "apollo", "scan.pdf", content_type="application/pdf")
    assert first != second


def test_download_returns_the_uploaded_bytes(bucket):
    key = s3.upload_file_to_s3(io.BytesIO(b"payload"), "apollo", "a.pdf", content_type="application/pdf")
    assert s3.download_file_from_s3(key) == b"payload"


def test_delete_removes_the_object(bucket):
    key = s3.upload_file_to_s3(io.BytesIO(b"x"), "apollo", "a.pdf", content_type="application/pdf")
    s3.delete_file_from_s3(key)
    listing = bucket.list_objects_v2(Bucket=settings.AWS_S3_BUCKET_NAME)
    assert listing.get("KeyCount", 0) == 0


def test_presigned_url_uses_sigv4_and_regional_endpoint(bucket):
    # Guards against the SignatureDoesNotMatch bug we hit in development.
    url = s3.generate_presigned_url("documents/apollo/x/scan.pdf", expiry=600)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.hostname == f"s3.{settings.AWS_S3_REGION}.amazonaws.com"
    assert settings.AWS_S3_BUCKET_NAME in parsed.path
    assert parsed.path.endswith("documents/apollo/x/scan.pdf")
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == ["600"]
    assert "X-Amz-Signature" in query