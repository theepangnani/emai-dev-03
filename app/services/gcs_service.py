from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_bucket():
    from google.cloud import storage
    client = storage.Client()
    return client.bucket(settings.gcs_bucket_name)


def upload_file(gcs_path: str, data: bytes, content_type: str) -> str:
    """Upload bytes to GCS. Returns the gcs_path."""
    bucket = get_bucket()
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(data, content_type=content_type)
    return gcs_path


def download_file(gcs_path: str) -> bytes:
    """Download file from GCS as bytes."""
    bucket = get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.download_as_bytes()


def delete_file(gcs_path: str) -> None:
    """Delete file from GCS. Logs warning if not found."""
    try:
        bucket = get_bucket()
        blob = bucket.blob(gcs_path)
        blob.delete()
    except Exception as e:
        logger.warning(f"GCS delete failed for {gcs_path}: {e}")
