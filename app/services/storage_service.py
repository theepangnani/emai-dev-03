import logging
from pathlib import Path
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_upload_dir = Path(settings.upload_dir)


def save_file(content: bytes, filename: str) -> str:
    """Save file content to uploads dir. Returns relative stored filename."""
    _upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower() if filename else ""
    stored_name = f"{uuid4().hex}{ext}"
    dest = _upload_dir / stored_name
    dest.write_bytes(content)
    logger.info("Saved uploaded file: %s (%d bytes)", stored_name, len(content))
    return stored_name


def get_file_path(relative_path: str) -> Path:
    """Resolve a stored filename to its absolute path."""
    return _upload_dir / relative_path


def delete_file(relative_path: str) -> None:
    """Delete a stored file. Silently ignores missing files."""
    try:
        path = _upload_dir / relative_path
        path.unlink(missing_ok=True)
        logger.info("Deleted stored file: %s", relative_path)
    except Exception as e:
        logger.warning("Failed to delete stored file %s: %s", relative_path, e)
