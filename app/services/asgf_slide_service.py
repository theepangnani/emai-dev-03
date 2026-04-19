"""
ASGF Slide Generation Service — generates 7-slide interactive mini-lessons
using Claude API with teacher vocabulary priority and source attribution.

Issue: #3398
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.ai_service import get_async_anthropic_client

logger = get_logger(__name__)

# 7-slide spec: each entry is (purpose, content_hint)
_SLIDE_SPEC: list[tuple[str, str]] = [
    (
        "Topic Intro",
        "Orient the student: topic name, 1-sentence definition, connection to the question.",
    ),
    (
        "Core Concept A",
        "First fundamental concept: 3-5 sentences, a visual analogy, key vocabulary.",
    ),
    (
        "Core Concept B",
        "Second fundamental concept: same structure as Concept A, connects to Slide 2.",
    ),
    (
        "Worked Example",
        "Applied concept from uploaded docs: step-by-step worked example.",
    ),
    (
        "Subject-Specific Samples",
        "Multiple difficulty levels: Easy / Medium / Challenge examples.",
    ),
    (
        "Direct Answer",
        "Answer the student's question: reference Slides 2-3, connect to uploaded docs.",
    ),
    (
        "Summary + Quiz Preview",
        "Consolidate: '3 things to remember' + quiz teaser.",
    ),
]

TOTAL_SLIDES = len(_SLIDE_SPEC)


class ASGFSlideService:
    """Generates 7-slide interactive mini-lesson content using Claude API."""

    async def generate_slides(
        self,
        learning_cycle_plan: dict,
        context_package: dict,
    ) -> AsyncGenerator[dict, None]:
        """Generate slides one at a time via SSE streaming.

        Yields slide dicts: {
            slide_number: int,
            title: str,
            body: str,           # markdown
            vocabulary_terms: list[str],
            source_attribution: str | None,
            read_more_content: str | None,
            bloom_tier: str,
        }
        """
        system_prompt = self._build_slide_system_prompt(context_package)
        client = get_async_anthropic_client()

        def _error_placeholder(slide_number: int) -> dict:
            purpose, _ = _SLIDE_SPEC[slide_number - 1]
            return {
                "slide_number": slide_number,
                "title": f"Slide {slide_number} — {purpose}",
                "body": "Content generation failed. Please try again.",
                "vocabulary_terms": [],
                "source_attribution": None,
                "read_more_content": None,
                "bloom_tier": "understand",
                "error": True,
            }

        # Slide #1 synchronously first for fastest time-to-first-paint.
        try:
            slide_one = await self._generate_single_slide(
                client=client,
                system_prompt=system_prompt,
                learning_cycle_plan=learning_cycle_plan,
                context_package=context_package,
                slide_number=1,
            )
            yield slide_one
        except Exception as e:
            logger.error("ASGF slide generation failed for slide %d: %s", 1, e)
            yield _error_placeholder(1)

        if TOTAL_SLIDES < 2:
            return

        # Slides #2-7: bounded concurrency, in-order emission.
        semaphore = asyncio.Semaphore(3)

        async def _run_with_semaphore(slide_number: int) -> dict:
            async with semaphore:
                return await self._generate_single_slide(
                    client=client,
                    system_prompt=system_prompt,
                    learning_cycle_plan=learning_cycle_plan,
                    context_package=context_package,
                    slide_number=slide_number,
                )

        tasks: dict[asyncio.Task, int] = {}
        for slide_number in range(2, TOTAL_SLIDES + 1):
            task = asyncio.create_task(_run_with_semaphore(slide_number))
            tasks[task] = slide_number

        try:
            buffered: dict[int, dict] = {}
            next_to_yield = 2
            pending = set(tasks.keys())

            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    slide_number = tasks[task]
                    try:
                        buffered[slide_number] = task.result()
                    except Exception as e:
                        logger.error(
                            "ASGF slide generation failed for slide %d: %s",
                            slide_number,
                            e,
                        )
                        buffered[slide_number] = _error_placeholder(slide_number)

                while next_to_yield in buffered:
                    yield buffered.pop(next_to_yield)
                    next_to_yield += 1
        finally:
            # Cancel any tasks still running (e.g. generator closed early)
            # to prevent Claude token leaks for slides the user won't see.
            if tasks:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_slide_system_prompt(self, context_package: dict) -> str:
        """Build the system prompt emphasizing teacher vocabulary priority.

        CRITICAL RULE: Use the teacher's exact vocabulary, examples, and
        notation from the uploaded class notes. Only fall back to
        curriculum-standard language for concepts NOT covered in the
        teacher's notes.
        """
        # Collect source filenames for reference
        doc_meta = context_package.get("document_metadata", [])
        source_names = [d.get("filename", "unknown") for d in doc_meta]

        # Collect teacher vocabulary from extracted concepts
        concepts = context_package.get("concepts", [])
        teacher_vocab: list[str] = []
        for c in concepts:
            teacher_vocab.extend(c.get("vocabulary_terms", []))
        teacher_vocab = list(dict.fromkeys(teacher_vocab))  # dedupe, preserve order

        # Collect examples from teacher docs
        teacher_examples: list[str] = []
        for c in concepts:
            teacher_examples.extend(c.get("examples", []))
        teacher_examples = teacher_examples[:10]  # cap at 10

        # Pull grade level from context for the constraint block
        grade_level = context_package.get("grade_level", "")

        prompt_parts = [
            "You are an expert educational content creator building interactive "
            "mini-lesson slides for a student.",
            "",
        ]

        if grade_level:
            prompt_parts.extend([
                "=== GRADE LEVEL CONSTRAINT ===",
                f"All content MUST be appropriate for {grade_level}. Vocabulary, sentence complexity, "
                "and examples must match this grade level.",
                "",
            ])

        prompt_parts.extend([
            "=== CRITICAL RULE: TEACHER VOCABULARY PRIORITY ===",
            "Use the teacher's exact vocabulary, examples, and notation from the "
            "uploaded class notes. Only fall back to curriculum-standard language "
            "for concepts NOT covered in the teacher's notes.",
            "",
            "When a teacher's document uses a specific term (e.g. 'rate of change' "
            "vs 'slope'), ALWAYS prefer the teacher's term. The student learns "
            "from this teacher and must recognize the same language in class.",
            "",
        ])

        if teacher_vocab:
            prompt_parts.append("=== TEACHER VOCABULARY (use these exact terms) ===")
            prompt_parts.append(", ".join(teacher_vocab[:50]))
            prompt_parts.append("")

        if teacher_examples:
            prompt_parts.append("=== TEACHER EXAMPLES (incorporate where relevant) ===")
            for ex in teacher_examples:
                prompt_parts.append(f"- {ex}")
            prompt_parts.append("")

        if source_names:
            prompt_parts.append("=== UPLOADED DOCUMENTS ===")
            for name in source_names:
                prompt_parts.append(f"- {name}")
            prompt_parts.append("")

        prompt_parts.extend([
            "=== OUTPUT FORMAT ===",
            "Return ONLY valid JSON with these fields:",
            "- title (string): slide title",
            "- body (string): markdown content for the slide",
            "- vocabulary_terms (list[string]): key terms used in this slide",
            "- source_attribution (string|null): which uploaded document informed "
            "this slide, e.g. 'From your class notes (Unit3_Notes.pdf)'",
            "- read_more_content (string|null): optional additional detail the "
            "student can expand to read",
            "- bloom_tier (string): one of 'remember', 'understand', 'apply', "
            "'analyze', 'evaluate', 'create'",
            "",
            "Return ONLY the JSON object. No markdown fences, no extra text.",
        ])

        return "\n".join(prompt_parts)

    def _build_slide_user_prompt(
        self, learning_cycle_plan: dict, slide_number: int
    ) -> str:
        """Build per-slide generation prompt."""
        purpose, content_hint = _SLIDE_SPEC[slide_number - 1]
        question = learning_cycle_plan.get("question", "")
        subject = learning_cycle_plan.get("subject", "")
        topic = learning_cycle_plan.get("topic", "")
        grade_level = learning_cycle_plan.get("grade_level", "")
        bloom_tier = learning_cycle_plan.get("bloom_tier", "understand")

        # Include concept summaries from the plan if available
        concept_summaries = learning_cycle_plan.get("concept_summaries", [])
        concept_text = ""
        if concept_summaries:
            concept_text = "\n\nKey concepts from uploaded documents:\n"
            for cs in concept_summaries[:8]:
                name = cs if isinstance(cs, str) else cs.get("concept_name", "")
                concept_text += f"- {name}\n"

        prompt = (
            f"Generate Slide {slide_number} of 7.\n\n"
            f"SLIDE PURPOSE: {purpose}\n"
            f"CONTENT GUIDE: {content_hint}\n\n"
            f"STUDENT QUESTION: {question}\n"
            f"SUBJECT: {subject}\n"
            f"TOPIC: {topic}\n"
            f"GRADE LEVEL: {grade_level}\n"
            f"TARGET BLOOM TIER: {bloom_tier}\n"
            f"{concept_text}\n"
            "Remember: use the teacher's exact vocabulary and examples. "
            "Attribute content to the source document when applicable."
        )
        return prompt

    # ------------------------------------------------------------------
    # Single-slide generation
    # ------------------------------------------------------------------

    async def _generate_single_slide(
        self,
        client,
        system_prompt: str,
        learning_cycle_plan: dict,
        context_package: dict,
        slide_number: int,
    ) -> dict:
        """Generate a single slide using Claude API."""
        user_prompt = self._build_slide_user_prompt(learning_cycle_plan, slide_number)

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.4,
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
        raw = raw.strip()

        try:
            slide_data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "ASGF slide %d: JSON parse failed, raw=%s", slide_number, raw[:200]
            )
            purpose, _ = _SLIDE_SPEC[slide_number - 1]
            slide_data = {
                "title": f"Slide {slide_number} — {purpose}",
                "body": raw,  # return raw text as body fallback
                "vocabulary_terms": [],
                "source_attribution": None,
                "read_more_content": None,
                "bloom_tier": "understand",
            }

        # Normalise and add slide_number
        slide_data["slide_number"] = slide_number
        slide_data.setdefault("title", f"Slide {slide_number}")
        slide_data.setdefault("body", "")
        slide_data.setdefault("vocabulary_terms", [])
        slide_data.setdefault("source_attribution", None)
        slide_data.setdefault("read_more_content", None)
        slide_data.setdefault("bloom_tier", "understand")

        logger.info(
            "ASGF slide %d generated: title=%s, tokens_in=%d, tokens_out=%d",
            slide_number,
            slide_data.get("title", ""),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return slide_data
