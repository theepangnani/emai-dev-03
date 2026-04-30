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

    Cloud Run ADC compatibility
    ---------------------------
    On Cloud Run, the default Application Default Credentials don't
    carry a private key (they're metadata-server tokens), so a naive
    ``blob.generate_signed_url(version="v4")`` raises
    ``AttributeError: you need a private key to sign credentials``.
    We refresh the runtime ADC credentials and pass them through
    ``service_account_email`` + ``access_token`` so V4 signing falls back
    to the IAM ``signBlob`` path. This works on:

    - Cloud Run (metadata-server ADC) — uses IAM signBlob.
    - Local dev with a service-account JSON file — uses the embedded
      private key.
    - CI / unit tests — mocked at the ``gcs_service`` module level so
      this code path is never exercised; tests patch the helper itself.

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

    # Refresh ADC + pass service_account_email + access_token so V4
    # signing works with metadata-server credentials (Cloud Run).
    # Falls through to the embedded-private-key path when the runtime
    # ADC already carries a private key (local dev with SA JSON).
    try:
        from google.auth import default as _default_credentials
        from google.auth.transport import requests as _ga_requests

        creds, _ = _default_credentials()
        if not creds.valid:
            creds.refresh(_ga_requests.Request())
        service_account_email = getattr(creds, "service_account_email", None)
        access_token = getattr(creds, "token", None)
    except Exception as e:  # pragma: no cover — defensive; tests mock helper
        logger.warning(
            "generate_signed_url: ADC fetch failed (%s); attempting "
            "default V4 signing path", e,
        )
        service_account_email = None
        access_token = None

    kwargs: dict = {
        "version": "v4",
        "expiration": timedelta(seconds=ttl_seconds),
        "method": "GET",
    }
    if service_account_email and access_token:
        kwargs["service_account_email"] = service_account_email
        kwargs["access_token"] = access_token

    return blob.generate_signed_url(**kwargs)
