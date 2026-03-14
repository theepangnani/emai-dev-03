#!/usr/bin/env python3
"""
Backfill existing DB blobs to GCS.

Usage:
    python scripts/backfill_blobs_to_gcs.py [--dry-run] [--batch-size 50]

Idempotent: skips records that already have gcs_path set.
Logs progress and failures without aborting.
"""
import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.source_file import SourceFile
from app.models.content_image import ContentImage
from app.services import gcs_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/tiff": "tiff",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
    "image/heic": "heic",
    "image/heif": "heif",
}


def _image_ext(media_type: str | None) -> str:
    """Return file extension for a MIME type, defaulting to 'jpg'."""
    return MIME_TO_EXT.get((media_type or "").lower(), "jpg")


def backfill_source_files(session, dry_run: bool, batch_size: int):
    """Migrate SourceFile blobs to GCS."""
    total = session.query(SourceFile).filter(
        SourceFile.gcs_path == None,
        SourceFile.file_data != None
    ).count()
    logger.info(f"SourceFile: {total} records to migrate")

    migrated = 0
    failed = 0
    processed_ids: set = set()

    while True:
        records = (
            session.query(SourceFile)
            .filter(SourceFile.gcs_path == None, SourceFile.file_data != None)
            .filter(~SourceFile.id.in_(processed_ids) if processed_ids else True)
            .limit(batch_size)
            .all()
        )
        if not records:
            break

        for record in records:
            processed_ids.add(record.id)
            gcs_path = f"source-files/{record.course_content_id}/{record.id}/{record.filename}"
            try:
                if not dry_run:
                    gcs_service.upload_file(gcs_path, record.file_data, record.file_type or "application/octet-stream")
                    record.gcs_path = gcs_path
                    record.file_data = None
                logger.info(f"  [{'DRY' if dry_run else 'OK'}] SourceFile {record.id} -> {gcs_path}")
                migrated += 1
            except Exception as e:
                logger.warning(f"  [FAIL] SourceFile {record.id}: {e}")
                failed += 1

        if not dry_run:
            session.commit()

        logger.info(f"Progress: {len(processed_ids)}/{total} processed ({failed} failed)")

    return migrated, failed


def backfill_content_images(session, dry_run: bool, batch_size: int):
    """Migrate ContentImage blobs to GCS."""
    total = session.query(ContentImage).filter(
        ContentImage.gcs_path == None,
        ContentImage.image_data != None
    ).count()
    logger.info(f"ContentImage: {total} records to migrate")

    migrated = 0
    failed = 0
    processed_ids: set = set()

    while True:
        records = (
            session.query(ContentImage)
            .filter(ContentImage.gcs_path == None, ContentImage.image_data != None)
            .filter(~ContentImage.id.in_(processed_ids) if processed_ids else True)
            .limit(batch_size)
            .all()
        )
        if not records:
            break

        for record in records:
            processed_ids.add(record.id)
            ext = _image_ext(record.media_type)
            gcs_path = f"content-images/{record.course_content_id}/{record.id}.{ext}"
            try:
                if not dry_run:
                    gcs_service.upload_file(gcs_path, record.image_data, record.media_type or "image/jpeg")
                    record.gcs_path = gcs_path
                    record.image_data = None
                logger.info(f"  [{'DRY' if dry_run else 'OK'}] ContentImage {record.id} -> {gcs_path}")
                migrated += 1
            except Exception as e:
                logger.warning(f"  [FAIL] ContentImage {record.id}: {e}")
                failed += 1

        if not dry_run:
            session.commit()

        logger.info(f"Progress: {len(processed_ids)}/{total} processed ({failed} failed)")

    return migrated, failed


def main():
    parser = argparse.ArgumentParser(description="Backfill DB blobs to GCS")
    parser.add_argument("--dry-run", action="store_true", help="Log what would happen without making changes")
    parser.add_argument("--batch-size", type=int, default=50, help="Records per batch (default: 50)")
    args = parser.parse_args()

    if not settings.gcs_bucket_name:
        logger.error("GCS_BUCKET_NAME is not set. Aborting.")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE — no changes will be made")

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        sf_migrated, sf_failed = backfill_source_files(session, args.dry_run, args.batch_size)
        ci_migrated, ci_failed = backfill_content_images(session, args.dry_run, args.batch_size)

        logger.info(f"\n=== DONE ===")
        logger.info(f"SourceFiles:    {sf_migrated} migrated, {sf_failed} failed")
        logger.info(f"ContentImages:  {ci_migrated} migrated, {ci_failed} failed")

        if sf_failed + ci_failed > 0:
            logger.warning("Some records failed — re-run to retry failed items")
            sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
