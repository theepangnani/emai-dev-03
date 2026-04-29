"""
Parent Companion Generation Service (CB-CMCP-001 M1-F 1F-1, #4463; M1-F 1F-2, #4474).

Initial port of phase-2 ParentSummaryService (`c:/dev/emai/class-bridge-phase-2/
app/services/parent_summary.py`, 116 LOC). 1F-1 ports the existing service as-is;
1F-2 (this stripe) ADDS the 5-section structured output method
`generate_5_section()` per FR-02.6 / Amendment A2.

Generates a parent-facing companion alongside every student study guide.
This is ClassBridge's unique "Parent Visibility Layer" differentiator.

Example legacy `generate()` output:
"Haashini is preparing for a Grade 8 science lab on cell division.
Here are 3 ways you can support her tonight:
1. Ask her to explain the difference between mitosis and meiosis
2. Help her review the key vocabulary terms highlighted in yellow
3. Quiz her on the practice questions at the end of the study guide"

The new `generate_5_section()` produces a structured `ParentCompanionContent`
with: SE explanation (2 sentences), talking points (3-5), coaching prompts,
"how to help without giving the answer" guidance, and a Bridge deep-link payload.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from app.core.logging_config import get_logger
from app.services.ai_service import generate_content

logger = get_logger(__name__)

# Maximum length of the study guide excerpt fed to the AI (controls prompt cost).
MAX_GUIDE_EXCERPT_CHARS = 2000

# Talking-points configurable bounds (FR-02.6).
MIN_TALKING_POINTS = 3
MAX_TALKING_POINTS = 5

# Auditable lint markers — output MUST NOT contain answer keys (A2 acceptance).
# Matched case-insensitively. Substring patterns deliberately conservative to
# avoid false positives on legitimate parent-facing prose (e.g. "your answer
# might be that..." would falsely trip "answer:" so we require explicit markers).
ANSWER_KEY_MARKERS: tuple[str, ...] = (
    "answer:",
    "answer key",
    "the answer is",
    "correct answer",
    "solution:",
)

PARENT_COMPANION_SYSTEM_PROMPT = """You are a friendly educational assistant on ClassBridge, a K-12 education platform.
You are writing a brief summary for a PARENT (not the student). Your goal is to help the parent understand what their child is studying and give them 3 specific, actionable ways to support their child's learning tonight.

Guidelines:
- Use warm, encouraging language
- Keep it short (150-200 words max)
- Always include exactly 3 numbered action items
- Use the child's name if provided
- Mention the subject/topic clearly
- Make action items specific and practical (not generic like "help them study")
- Do NOT include any markdown headers or complex formatting — use plain text with numbered lists"""


PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT = """You are a friendly educational coach on ClassBridge, a K-12 education platform.
You are writing a structured companion for a PARENT (not the student) so they can support their child's learning at home WITHOUT giving away answers.

You MUST respond with a single JSON object — no markdown fences, no preamble, no commentary. The JSON object MUST match this exact schema:

{
  "se_explanation": "<plain-language explanation of what the child is learning this week, in EXACTLY 2 sentences. No jargon. No curriculum codes.>",
  "talking_points": ["<short conversation starter 1>", "<short conversation starter 2>", "..."],
  "coaching_prompts": ["<open-ended question 1>", "<open-ended question 2>", "..."],
  "how_to_help_without_giving_answer": "<one short paragraph (2-4 sentences) of practical guidance on supporting the child without revealing solutions>"
}

Hard rules:
- DO NOT include any answer keys, worked solutions, or final numeric/textual answers anywhere in the JSON.
- DO NOT use phrases like "answer:", "the answer is", "correct answer", "solution:", or "answer key".
- Coaching prompts must be open-ended questions the parent can ask the child — not statements with embedded answers.
- "how_to_help_without_giving_answer" must explicitly favour questions, hints, and process over revealing answers.
- Use the child's name if provided. Keep tone warm and encouraging.
- Output PURE JSON only. No surrounding text, no code fences."""


class BridgeDeepLinkPayload(BaseModel):
    """Typed payload for the Bridge deep link (rendered in 1F-4).

    Builds a contract for the next stripe so consumers get static field
    validation rather than untyped dict access.
    """

    child_id: int | str | None = None
    week_summary: str | None = None
    deep_link_target: str | None = None


class ParentCompanionContent(BaseModel):
    """Structured 5-section parent companion output (FR-02.6 / A2).

    Fields 1-4 are model-generated; field 5 (`bridge_deep_link_payload`) is
    constructed by the service from caller-provided context — its render is
    out of scope for 1F-2 (lands in 1F-4).
    """

    se_explanation: str = Field(
        ..., description="Plain-language explanation of what the child is learning, in 2 sentences."
    )
    talking_points: list[str] = Field(
        ...,
        min_length=MIN_TALKING_POINTS,
        max_length=MAX_TALKING_POINTS,
        description="3-5 talking points the parent can use at home.",
    )
    coaching_prompts: list[str] = Field(
        ..., description="Open-ended questions the parent can ask to check understanding."
    )
    how_to_help_without_giving_answer: str = Field(
        ..., description="Guidance for the parent on supporting the child without revealing answers."
    )
    bridge_deep_link_payload: BridgeDeepLinkPayload = Field(
        default_factory=BridgeDeepLinkPayload,
        description="Payload for the Bridge deep link (rendered in 1F-4).",
    )


def _strip_json_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences if the model wrapped the JSON anyway."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop leading fence (```json or ```)
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        # Drop trailing fence
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        stripped = stripped.strip()
    return stripped


def _contains_answer_key_markers(text: str) -> tuple[bool, str | None]:
    """Auditable lint: check the text for forbidden answer-key markers.

    Returns (True, marker) if any marker is present, else (False, None).
    The match is case-insensitive AND whitespace-tolerant: the text is
    lowercased, runs of whitespace are collapsed to a single space, and
    whitespace adjacent to punctuation (``:``) is stripped before substring
    matching. Adversarial variants like ``"answer :"`` (space before colon),
    ``"the  answer  is"`` (double-space), or ``"ANSWER:\\t42"`` all trip the
    lint the same as their canonical form.
    """
    if not text:
        return False, None
    # Normalize: lowercase, collapse whitespace, strip whitespace around colons.
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*:\s*", ":", normalized)
    for marker in ANSWER_KEY_MARKERS:
        if marker in normalized:
            return True, marker
    return False, None


def _scan_content_for_answer_keys(content: ParentCompanionContent) -> tuple[bool, str | None]:
    """Scan every text field of the structured content for answer-key markers.

    NOTE: ``bridge_deep_link_payload`` is intentionally excluded — it is
    built from caller-provided structured fields (child_id, week_summary,
    deep_link_target), not model output, so it cannot leak answer keys
    from the AI response.
    """
    text_fields: list[str] = [
        content.se_explanation,
        content.how_to_help_without_giving_answer,
        *content.talking_points,
        *content.coaching_prompts,
    ]
    for field_text in text_fields:
        hit, marker = _contains_answer_key_markers(field_text)
        if hit:
            return True, marker
    return False, None


class ParentCompanionService:
    """Service for generating parent-facing study guide summaries."""

    @staticmethod
    async def generate(
        study_guide_content: str,
        student_name: str | None = None,
        subject: str | None = None,
        document_type: str | None = None,
        study_goal: str | None = None,
    ) -> str | None:
        """
        Generate a parent-facing summary from a student's study guide.

        Args:
            study_guide_content: The full study guide content (markdown)
            student_name: The student's name (for personalization)
            subject: The course/subject name
            document_type: The document type classification
            study_goal: What the student is preparing for

        Returns:
            Parent summary text, or None if generation fails
        """
        if not study_guide_content or not study_guide_content.strip():
            return None

        name = student_name or "your child"
        subj = subject or "their course material"

        context_parts = [f"The student ({name}) is studying {subj}."]

        if document_type:
            type_labels = {
                "teacher_notes": "teacher's class notes",
                "course_syllabus": "course syllabus",
                "past_exam": "a past exam/test",
                "mock_exam": "a practice exam",
                "project_brief": "a project assignment",
                "lab_experiment": "a lab experiment",
                "textbook_excerpt": "a textbook reading",
            }
            label = type_labels.get(document_type, "study material")
            context_parts.append(f"They uploaded {label}.")

        if study_goal:
            goal_labels = {
                "upcoming_test": "an upcoming test or quiz",
                "final_exam": "their final exam",
                "assignment": "an assignment submission",
                "lab_prep": "a lab session",
                "general_review": "a general review of the material",
                "discussion": "a class discussion or presentation",
                "parent_review": "a parent-assisted review session",
            }
            goal = goal_labels.get(study_goal, "studying")
            context_parts.append(f"They are preparing for {goal}.")

        context = " ".join(context_parts)

        # Use first 2000 chars of study guide to keep costs low
        guide_excerpt = study_guide_content[:2000]

        prompt = f"""{context}

Here is an excerpt from the study guide that was generated for them:

---
{guide_excerpt}
---

Write a brief parent-facing summary. Start with one sentence describing what {name} is working on. Then provide exactly 3 numbered action items for how the parent can help tonight."""

        try:
            content, _ = await generate_content(
                prompt=prompt,
                system_prompt=PARENT_COMPANION_SYSTEM_PROMPT,
                max_tokens=500,
                temperature=0.7,
            )
            logger.info(f"Generated parent companion summary ({len(content)} chars) for student={student_name}")
            return content.strip()
        except Exception as e:
            logger.warning(f"Parent companion summary generation failed: {e}")
            return None

    @staticmethod
    async def generate_5_section(
        study_guide_content: str,
        student_name: str | None = None,
        subject: str | None = None,
        target_se_codes: list[str] | None = None,
        target_se_descriptions: list[str] | None = None,
        talking_points_count: int = 3,
        child_id: int | str | None = None,
        deep_link_target: str | None = None,
        week_summary: str | None = None,
    ) -> ParentCompanionContent | None:
        """Generate a 5-section structured parent companion (FR-02.6 / A2).

        Sections produced:
            1. ``se_explanation`` — plain-language summary, 2 sentences.
            2. ``talking_points`` — 3-5 items (clamped to ``talking_points_count``).
            3. ``coaching_prompts`` — open-ended questions for the parent.
            4. ``how_to_help_without_giving_answer`` — guidance paragraph.
            5. ``bridge_deep_link_payload`` — payload only; render is 1F-4.

        Args:
            study_guide_content: The full study guide content (markdown).
            student_name: The student's name (for personalization).
            subject: The course/subject name.
            target_se_codes: Curriculum SE codes the guide targets (optional).
            target_se_descriptions: Plain-language descriptions of the SE codes
                (optional). Fed to the model so it can produce parent-readable
                explanation without leaking codes.
            talking_points_count: Desired number of talking points
                (clamped to [MIN_TALKING_POINTS, MAX_TALKING_POINTS]).
            child_id: Child identifier embedded in the deep-link payload.
            deep_link_target: Bridge deep-link target route/key (1F-4 wires this).
            week_summary: Short label for the parent-facing week summary (e.g.
                "Week of Apr 27"). Stored verbatim in the deep-link payload.

        Returns:
            ``ParentCompanionContent`` on success, or ``None`` if generation
            fails for any reason (logged, never raised — matches ``generate()``).
        """
        if not study_guide_content or not study_guide_content.strip():
            return None

        # Clamp talking_points_count to the FR-02.6 [3, 5] band.
        clamped_count = max(MIN_TALKING_POINTS, min(MAX_TALKING_POINTS, talking_points_count))

        name = student_name or "your child"
        subj = subject or "their course material"

        context_parts = [f"The student ({name}) is studying {subj}."]

        if target_se_descriptions:
            descriptions = "; ".join(target_se_descriptions[:5])
            context_parts.append(
                f"This week's learning targets (in plain language): {descriptions}."
            )
        elif target_se_codes:
            # Fall back to codes only — the prompt already forbids leaking codes
            # in the parent-facing output, so the model is expected to translate.
            codes = ", ".join(target_se_codes[:5])
            context_parts.append(
                f"Internal curriculum targets (DO NOT include these codes in your output): {codes}."
            )

        context = " ".join(context_parts)
        guide_excerpt = study_guide_content[:MAX_GUIDE_EXCERPT_CHARS]

        prompt = f"""{context}

Here is an excerpt from the study guide that was generated for the student:

---
{guide_excerpt}
---

Produce the 5-section parent companion as PURE JSON per the system schema.
Provide EXACTLY {clamped_count} talking_points. Provide between 2 and 4 coaching_prompts.
Do not reveal answers anywhere in the JSON."""

        try:
            raw_content, _ = await generate_content(
                prompt=prompt,
                system_prompt=PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT,
                max_tokens=900,
                temperature=0.5,
            )
        except Exception as e:
            logger.warning(f"Parent companion 5-section generation failed (AI call): {e}")
            return None

        if not raw_content or not raw_content.strip():
            logger.warning("Parent companion 5-section generation: empty AI response")
            return None

        # Parse the JSON body the model returned (tolerate stray code fences).
        try:
            cleaned = _strip_json_fences(raw_content)
            payload = json.loads(cleaned)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Parent companion 5-section: JSON parse failed: {e}")
            return None

        if not isinstance(payload, dict):
            logger.warning("Parent companion 5-section: AI response was not a JSON object")
            return None

        # Build the deep-link payload from caller-provided context.
        bridge_deep_link_payload = BridgeDeepLinkPayload(
            child_id=child_id,
            week_summary=week_summary,
            deep_link_target=deep_link_target,
        )

        try:
            content = ParentCompanionContent(
                se_explanation=payload.get("se_explanation", ""),
                talking_points=payload.get("talking_points", []),
                coaching_prompts=payload.get("coaching_prompts", []),
                how_to_help_without_giving_answer=payload.get(
                    "how_to_help_without_giving_answer", ""
                ),
                bridge_deep_link_payload=bridge_deep_link_payload,
            )
        except ValidationError as e:
            logger.warning(f"Parent companion 5-section: schema validation failed: {e}")
            return None

        # Auditable answer-key lint — A2 acceptance criterion.
        hit, marker = _scan_content_for_answer_keys(content)
        if hit:
            logger.warning(
                f"Parent companion 5-section: rejected — answer-key marker '{marker}' "
                f"detected in model output for student={student_name}"
            )
            return None

        logger.info(
            f"Generated 5-section parent companion (talking_points={len(content.talking_points)}, "
            f"coaching_prompts={len(content.coaching_prompts)}) for student={student_name}"
        )
        return content
