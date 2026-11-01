import boto3
import uuid
from django.conf import settings


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=f"https://s3.{settings.AWS_S3_REGION}.amazonaws.com",
        config=boto3.session.Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"}
        ),
    )


def upload_file_to_s3(file_obj, organization_slug, original_filename):
    """
    Uploads a file to S3 and returns the file key.
    Path pattern: documents/{org_slug}/{uuid}/{filename}
    """
    ext = original_filename.split(".")[-1].lower()
    file_key = f"documents/{organization_slug}/{uuid.uuid4()}/{original_filename}"

    s3 = get_s3_client()
    s3.upload_fileobj(
        file_obj,
        settings.AWS_S3_BUCKET_NAME,
        file_key,
        ExtraArgs={"ContentType": f"application/{ext}"},
    )
    return file_key


def generate_presigned_url(file_key, expiry=3600):
    """
    Generates a temporary signed URL to access a private S3 file.
    Default expiry: 1 hour.
    """
    s3 = get_s3_client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_S3_BUCKET_NAME,
            "Key": file_key,
        },
        ExpiresIn=expiry,
    )
    return url


def delete_file_from_s3(file_key):
    """Deletes a file from S3 by its key."""
    s3 = get_s3_client()
    s3.delete_object(
        Bucket=settings.AWS_S3_BUCKET_NAME,
        Key=file_key,
    )