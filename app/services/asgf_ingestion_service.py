"""
ASGF Document Ingestion Pipeline — 6-stage text extraction, concept extraction,
relevance scoring, source attribution, and gap detection.

Issue: #3394
"""

import asyncio
import io
import json
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import openai

try:
    import PyPDF2
except ImportError:  # pragma: no cover
    PyPDF2 = None  # type: ignore[assignment]

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.ai_service import get_async_anthropic_client
from app.services.asgf_ocr_service import (
    extract_text_with_gcp_vision,
    is_gcp_vision_configured,
)
from app.services.file_processor import (
    IMAGE_EXTENSIONS,
    FileProcessingError,
    extract_text_from_docx,
    extract_text_from_image,
    extract_text_from_pdf,
    process_file,
    validate_file,
)

logger = get_logger(__name__)

# Relevance score threshold — concepts below this are filtered out
_RELEVANCE_THRESHOLD = 0.3


class ASGFIngestionService:
    """Six-stage document ingestion pipeline for ASGF slide generation."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def process_documents(
        self,
        files: list[dict],
        question: str,
        student_id: str | None = None,
    ) -> dict:
        """Run the full 6-stage pipeline and return a context package.

        Args:
            files: List of dicts with keys ``filename`` (str) and ``content`` (bytes).
            question: The user's question / topic for the presentation.
            student_id: Optional student ID for gap detection (stage 6).

        Returns:
            Context package dict ready for downstream slide generation.
        """
        start_ms = time.time()

        # Stage 1 + 2: format detection and text extraction (parallelised per file)
        extraction_tasks = [
            self._extract_single_file(f) for f in files
        ]
        extraction_results: list[dict] = await asyncio.gather(*extraction_tasks)

        # Stage 3: concept extraction (parallelised per document)
        concept_tasks = [
            self._stage3_extract_concepts(r["text"], r["filename"])
            for r in extraction_results
            if r["text"]
        ]
        nested_concepts: list[list[dict]] = await asyncio.gather(*concept_tasks)
        all_concepts: list[dict] = [c for batch in nested_concepts for c in batch]

        # Stage 4: relevance scoring
        scored_concepts = await self._stage4_score_relevance(all_concepts, question)

        # Stage 5: source attribution (enriches in-place)
        attributed_concepts = await self._stage5_attribute_sources(scored_concepts)

        # Stage 6: gap detection
        gap_data = await self._stage6_detect_gaps(attributed_concepts, student_id)

        processing_time_ms = int((time.time() - start_ms) * 1000)

        return {
            "question": question,
            "concepts": attributed_concepts,
            "gap_data": gap_data,
            "document_metadata": [
                {
                    "filename": r["filename"],
                    "file_type": r["file_type"],
                    "page_count": r.get("page_count"),
                    "char_count": len(r["text"]) if r["text"] else 0,
                }
                for r in extraction_results
            ],
            "processing_time_ms": processing_time_ms,
        }

    # ------------------------------------------------------------------
    # Convenience wrapper that merges stages 1 + 2 per file
    # ------------------------------------------------------------------

    async def _extract_single_file(self, file: dict) -> dict:
        """Run stage 1 (format detection) then stage 2 (text extraction) for one file."""
        fmt = await self._stage1_detect_format(file)
        text = await self._stage2_extract_text(file, fmt["file_type"])
        return {
            "filename": file["filename"],
            "file_type": fmt["file_type"],
            "page_count": fmt.get("page_count"),
            "text": text,
        }

    # ------------------------------------------------------------------
    # Stage 1 — Format detection
    # ------------------------------------------------------------------

    async def _stage1_detect_format(self, file: dict) -> dict:
        """Detect file type from extension and return metadata dict."""
        filename: str = file["filename"]
        content: bytes = file["content"]
        ext = Path(filename).suffix.lower()

        file_type = "unknown"
        if ext == ".pdf":
            file_type = "pdf"
        elif ext in (".docx", ".doc"):
            file_type = "docx"
        elif ext in IMAGE_EXTENSIONS:
            file_type = ext.lstrip(".")
        elif ext in (".txt", ".md"):
            file_type = "text"
        elif ext in (".pptx",):
            file_type = "pptx"
        elif ext in (".xlsx",):
            file_type = "xlsx"

        page_count = None
        if file_type == "pdf" and PyPDF2 is not None:
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                page_count = len(reader.pages)
            except Exception:
                pass

        logger.info("ASGF stage-1: detected %s as %s", filename, file_type)
        return {"file_type": file_type, "page_count": page_count}

    # ------------------------------------------------------------------
    # Stage 2 — Text extraction (reuses file_processor.py)
    # ------------------------------------------------------------------

    async def _stage2_extract_text(self, file: dict, file_type: str) -> str:
        """Extract text using GCP Vision (if configured) or file_processor utilities."""
        filename: str = file["filename"]
        content: bytes = file["content"]
        ext = Path(filename).suffix.lower()

        try:
            # Validate first (size, extension, magic bytes)
            validate_file(content, filename)

            # For image files, try GCP Vision OCR first (better for handwriting)
            if ext in IMAGE_EXTENSIONS and is_gcp_vision_configured():
                gcp_text = await extract_text_with_gcp_vision(content, filename)
                if gcp_text:
                    logger.info(
                        "ASGF stage-2: GCP Vision OCR extracted %d chars from %s",
                        len(gcp_text),
                        filename,
                    )
                    return gcp_text
                # GCP Vision returned empty — fall through to Anthropic Vision
                logger.info(
                    "ASGF stage-2: GCP Vision returned no text for %s, "
                    "falling back to Anthropic Vision",
                    filename,
                )

            # Default path: delegate to the synchronous process_file via thread pool
            text = await asyncio.to_thread(process_file, content, filename)
            ocr_method = "Anthropic Vision" if ext in IMAGE_EXTENSIONS else "file_processor"
            logger.info(
                "ASGF stage-2: %s extracted %d chars from %s",
                ocr_method,
                len(text),
                filename,
            )
            return text
        except FileProcessingError:
            raise
        except Exception as e:
            logger.error("ASGF stage-2: extraction failed for %s: %s", filename, e)
            raise FileProcessingError(
                f"Failed to extract text from {filename}: {e}"
            )

    # ------------------------------------------------------------------
    # Stage 3 — Concept extraction via Claude
    # ------------------------------------------------------------------

    async def _stage3_extract_concepts(
        self, text: str, source_filename: str
    ) -> list[dict]:
        """Use Claude to extract structured educational concepts from text."""
        if not text or not text.strip():
            return []

        # Truncate very long documents to keep prompt within limits
        max_chars = 30_000
        truncated = text[:max_chars]

        system_prompt = (
            "You are an educational content analyst. Extract the key concepts from "
            "the provided document text. Output valid JSON only — no markdown fences."
        )

        user_prompt = (
            f"Source file: {source_filename}\n\n"
            f"Document text:\n{truncated}\n\n"
            "Extract the key educational concepts. For each concept return a JSON "
            "object with these fields:\n"
            "- concept_name (string): short name\n"
            "- vocabulary_terms (list[string]): key terms\n"
            "- examples (list[string]): concrete examples mentioned\n"
            "- question_patterns (list[string]): likely exam question patterns\n"
            "- difficulty_signal (string): one of 'basic', 'intermediate', 'advanced'\n"
            "- curriculum_strand (string): broad curriculum area\n"
            "- source_file (string): the source filename\n\n"
            "Return a JSON array of concept objects. Output ONLY the JSON array."
        )

        try:
            client = get_async_anthropic_client()
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[: raw.rfind("```")]
                raw = raw.strip()

            concepts: list[dict] = json.loads(raw)

            # Ensure source_file is set
            for c in concepts:
                c.setdefault("source_file", source_filename)

            logger.info(
                "ASGF stage-3: extracted %d concepts from %s",
                len(concepts),
                source_filename,
            )
            return concepts

        except json.JSONDecodeError as e:
            logger.warning(
                "ASGF stage-3: JSON parse failed for %s: %s", source_filename, e
            )
            return []
        except Exception as e:
            logger.error(
                "ASGF stage-3: concept extraction failed for %s: %s",
                source_filename,
                e,
            )
            return []

    # ------------------------------------------------------------------
    # Stage 4 — Relevance scoring via OpenAI GPT-4o-mini
    # ------------------------------------------------------------------

    async def _stage4_score_relevance(
        self, concepts: list[dict], question: str
    ) -> list[dict]:
        """Score each concept for relevance to the question using GPT-4o-mini.

        Concepts scoring below ``_RELEVANCE_THRESHOLD`` are filtered out.
        """
        if not concepts:
            return []

        if not settings.openai_api_key:
            logger.warning(
                "ASGF stage-4: OpenAI API key not configured — skipping scoring"
            )
            for c in concepts:
                c["relevance_score"] = 1.0
            return concepts

        concept_names = [c.get("concept_name", "") for c in concepts]
        prompt = (
            f"Question: {question}\n\n"
            "For each concept below, output a relevance score from 0.0 to 1.0 "
            "indicating how relevant it is to the question. Return ONLY a JSON "
            "array of numbers in the same order.\n\n"
            "Concepts:\n"
            + "\n".join(f"{i+1}. {name}" for i, name in enumerate(concept_names))
        )

        try:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key.strip())
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a relevance scorer. Output only a JSON array of "
                            "floats, one per concept."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[: raw.rfind("```")]
                raw = raw.strip()

            scores: list[float] = json.loads(raw)

            # Attach scores and filter
            scored: list[dict] = []
            for i, concept in enumerate(concepts):
                score = scores[i] if i < len(scores) else 0.5
                concept["relevance_score"] = round(float(score), 2)
                if concept["relevance_score"] >= _RELEVANCE_THRESHOLD:
                    scored.append(concept)

            logger.info(
                "ASGF stage-4: %d/%d concepts passed relevance threshold (%.1f)",
                len(scored),
                len(concepts),
                _RELEVANCE_THRESHOLD,
            )
            return scored

        except Exception as e:
            logger.error("ASGF stage-4: relevance scoring failed: %s", e)
            # Fallback — keep all concepts with a neutral score
            for c in concepts:
                c["relevance_score"] = 0.5
            return concepts

    # ------------------------------------------------------------------
    # Stage 5 — Source attribution
    # ------------------------------------------------------------------

    async def _stage5_attribute_sources(
        self, concepts: list[dict]
    ) -> list[dict]:
        """Ensure every concept carries its source_file for slide attribution."""
        for concept in concepts:
            concept.setdefault("source_file", "unknown")
        logger.info("ASGF stage-5: attributed sources for %d concepts", len(concepts))
        return concepts

    # ------------------------------------------------------------------
    # Stage 6 — Gap detection
    # ------------------------------------------------------------------

    async def _stage6_detect_gaps(
        self, concepts: list[dict], student_id: str | None = None
    ) -> dict:
        """Cross-reference concepts against student learning history.

        Returns gap data with weak topics and previously studied topics.
        If the learning_history table does not exist yet (depends on #3391),
        this stage is a no-op that returns empty gap data.
        """
        gap_data: dict = {
            "weak_topics": [],
            "previously_studied": [],
        }

        if not student_id:
            logger.info("ASGF stage-6: no student_id — skipping gap detection")
            return gap_data

        # learning_history table not yet available (#3391) — return empty data
        logger.info(
            "ASGF stage-6: gap detection is a no-op until learning_history "
            "table is available (#3391)"
        )
        return gap_data
