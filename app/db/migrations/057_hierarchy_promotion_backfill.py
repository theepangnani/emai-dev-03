"""Retroactive hierarchy promotion for pre-existing multi-file materials (#1809) + SourceFile backfill (#1841)."""

import re
import time

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    # Retroactive hierarchy promotion (#1809)
    try:
        # Find course_contents with 2+ source_files but no material_group_id
        candidates = conn.execute(text(
            "SELECT cc.id, cc.course_id, cc.title, cc.content_type, "
            "cc.created_by_user_id, cc.text_content "
            "FROM course_contents cc "
            "INNER JOIN source_files sf ON sf.course_content_id = cc.id "
            "WHERE cc.material_group_id IS NULL "
            "AND cc.archived_at IS NULL "
            "GROUP BY cc.id, cc.course_id, cc.title, cc.content_type, "
            "cc.created_by_user_id, cc.text_content "
            "HAVING COUNT(sf.id) >= 2"
        )).fetchall()

        promoted_count = 0
        for row in candidates:
            master_id = row[0]
            course_id = row[1]
            master_title = row[2]
            content_type = row[3]
            created_by = row[4]
            text_content = row[5] or ""

            # Generate a unique group ID
            group_id = int(time.time() * 1000 + master_id) % 2147483647

            # Promote master
            conn.execute(text(
                "UPDATE course_contents SET is_master = 'true', "
                "material_group_id = :gid WHERE id = :mid"
            ), {"gid": group_id, "mid": master_id})

            # Get source files for this master
            source_files = conn.execute(text(
                "SELECT id, filename, file_type, file_size, gcs_path "
                "FROM source_files WHERE course_content_id = :cid "
                "ORDER BY id"
            ), {"cid": master_id}).fetchall()

            # Parse text_content sections: --- [filename] ---\n...text...
            file_text_map: dict[str, str] = {}
            if text_content:
                sections = re.split(r'---\s*\[(.+?)\]\s*---', text_content)
                for i in range(1, len(sections) - 1, 2):
                    fname = sections[i].strip()
                    ftxt = sections[i + 1].strip() if i + 1 < len(sections) else ""
                    file_text_map[fname] = ftxt

            for part_num, sf_row in enumerate(source_files, start=1):
                sf_id = sf_row[0]
                sf_filename = sf_row[1]
                sf_file_type = sf_row[2]
                sf_file_size = sf_row[3]

                sub_title = f"{master_title} \u2014 Part {part_num}"
                sub_text = file_text_map.get(sf_filename, "")

                # Insert sub-material
                conn.execute(text(
                    "INSERT INTO course_contents "
                    "(course_id, title, content_type, created_by_user_id, "
                    "original_filename, file_size, mime_type, text_content, "
                    "parent_content_id, is_master, material_group_id) "
                    "VALUES (:course_id, :title, :ctype, :created_by, "
                    ":filename, :fsize, :mime, :txt, "
                    ":parent_id, 'false', :gid)"
                ), {
                    "course_id": course_id,
                    "title": sub_title,
                    "ctype": content_type,
                    "created_by": created_by,
                    "filename": sf_filename,
                    "fsize": sf_file_size,
                    "mime": sf_file_type,
                    "txt": sub_text,
                    "parent_id": master_id,
                    "gid": group_id,
                })

                # Get the newly inserted sub-material ID
                sub_id_row = conn.execute(text(
                    "SELECT id FROM course_contents "
                    "WHERE parent_content_id = :pid AND original_filename = :fn "
                    "AND material_group_id = :gid "
                    "ORDER BY id DESC LIMIT 1"
                ), {"pid": master_id, "fn": sf_filename, "gid": group_id}).fetchone()

                if sub_id_row:
                    # Re-point source file to the sub-material
                    conn.execute(text(
                        "UPDATE source_files SET course_content_id = :sub_id "
                        "WHERE id = :sf_id"
                    ), {"sub_id": sub_id_row[0], "sf_id": sf_id})

            promoted_count += 1

        conn.commit()
        if promoted_count:
            logger.info(
                "Retroactively promoted %d multi-file materials to hierarchy (#1809)",
                promoted_count,
            )
    except Exception as e:
        logger.error("Failed to promote pre-existing multi-file materials (#1809): %s", e)
        try:
            conn.rollback()
        except Exception:
            pass

    # Backfill SourceFile records (#1841)
    try:
        rows = conn.execute(text("""
            SELECT cc.id, cc.original_filename, cc.mime_type, cc.file_size
            FROM course_contents cc
            LEFT JOIN source_files sf ON sf.course_content_id = cc.id
            WHERE cc.original_filename IS NOT NULL
              AND sf.id IS NULL
        """)).fetchall()

        if rows:
            for row in rows:
                content_id, filename, mime_type, file_size = row
                gcs_path = f"source-files/{content_id}/{filename}"
                conn.execute(text("""
                    INSERT INTO source_files (course_content_id, filename, file_type, file_size, gcs_path)
                    VALUES (:content_id, :filename, :file_type, :file_size, :gcs_path)
                """), {
                    "content_id": content_id,
                    "filename": filename,
                    "file_type": mime_type,
                    "file_size": file_size,
                    "gcs_path": gcs_path,
                })
            conn.commit()
            logger.info("Backfilled %d SourceFile records from CourseContent file metadata (#1841)", len(rows))
    except Exception as e:
        logger.warning("SourceFile backfill failed (#1841): %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
