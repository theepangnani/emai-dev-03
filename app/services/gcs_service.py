from app.core.config import settings
import logging
from datetime import timedelta

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


def generate_signed_url(gcs_path: str, *, ttl_seconds: int = 3600) -> str:
    """Generate a V4 GET signed URL for a GCS object.

    Used by CB-CMCP-001 M3-E 3E-3 (#4660) to hand a board admin a TTL-
    limited download URL for a CSV catalog export. The bucket itself
    stays private — the signed URL is the only handle a caller has.

    Parameters
    ----------
    gcs_path:
        Object path within the configured bucket (no ``gs://`` prefix).
    ttl_seconds:
        Lifetime of the signed URL. Defaults to 1 hour (3600s) per the
        3E-3 spec. Caller decides; the function does not cap.
    """
    bucket = get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_seconds),
        method="GET",
    )
