from celery import shared_task

from apps.documents.models import Document
from apps.extraction.models import ExtractedRecord
from apps.extraction.services import run_extraction


def _set_status(document, status):
    document.status = status
    # updated_at must be listed or auto_now won't refresh it
    document.save(update_fields=["status", "updated_at"])


@shared_task(bind=True, max_retries=3)
def extract_document_task(self, document_id):
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return  # deleted before the worker got to it

    _set_status(document, "processing")

    try:
        run_extraction(document)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            # backoff: 30s, 60s, 120s
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

        # out of retries: record the failure
        _set_status(document, "failed")
        ExtractedRecord.objects.update_or_create(
            document=document,
            defaults={"error_message": str(exc)[:1000]},
        )
        return

    _set_status(document, "completed")