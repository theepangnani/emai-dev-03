"""
Ontario Curriculum Mapping Service (§6.105.5, #1977)

Post-generation annotation step: maps study guide key concepts to Ontario
curriculum expectation codes. This is ClassBridge's Priority 1 differentiator —
no standalone AI platform can generate this mapping without student context.

Example output:
[
    {"concept": "Quadratic equations", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
    {"concept": "Solving by factoring", "curriculum_code": "MTH1W-B2.4", "strand": "Number"}
]
"""
import json
from app.core.logging_config import get_logger
from app.services.ai_service import generate_content

logger = get_logger(__name__)

CURRICULUM_SYSTEM_PROMPT = """You are an Ontario curriculum specialist for a K-12 education platform called ClassBridge.
You map educational content to Ontario curriculum expectation codes.

You are familiar with:
- Ontario elementary curriculum (Grades 1-8)
- Ontario secondary curriculum (Grades 9-12, OSSD)
- Course codes like MTH1W, SNC1W, ENG1D, etc.
- Strand and expectation numbering (e.g., B2.3 means Strand B, Overall Expectation 2, Specific Expectation 3)

When you cannot find an exact curriculum code match, provide your best approximation with the strand and general expectation area. Always include the course code prefix.

Respond with ONLY a JSON array (no markdown fences, no explanation). Each item must have: concept, curriculum_code, strand."""


class CurriculumMappingService:
    """Service for annotating study guide concepts with Ontario curriculum codes."""

    @staticmethod
    async def annotate(
        study_guide_text: str,
        grade: int | None = None,
        subject: str | None = None,
        course_name: str | None = None,
    ) -> list[dict] | None:
        """
        Annotate study guide key concepts with Ontario curriculum expectation codes.

        Args:
            study_guide_text: The study guide content to annotate
            grade: Student's grade level (1-12)
            subject: Subject area (e.g., "Math", "Science", "English")
            course_name: Full course name for context

        Returns:
            List of dicts with keys: concept, curriculum_code, strand
            Returns None if annotation fails or insufficient context
        """
        if not study_guide_text or not study_guide_text.strip():
            return None

        # Build context
        context_parts = []
        if grade:
            context_parts.append(f"Grade: {grade}")
        if subject:
            context_parts.append(f"Subject: {subject}")
        if course_name:
            context_parts.append(f"Course: {course_name}")

        if not context_parts:
            logger.info("No grade/subject context for curriculum mapping, skipping")
            return None

        context = ", ".join(context_parts)

        # Use first 3000 chars of study guide
        guide_excerpt = study_guide_text[:3000]

        prompt = f"""Student context: {context}

Study guide content:
---
{guide_excerpt}
---

Identify the 3-8 most important concepts in this study guide and map each to the most relevant Ontario curriculum expectation code. Return a JSON array."""

        try:
            content, _ = await generate_content(
                prompt=prompt,
                system_prompt=CURRICULUM_SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.3,  # Lower temperature for more precise mapping
            )

            # Strip markdown fences if present
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            codes = json.loads(text)

            if not isinstance(codes, list):
                logger.warning("Curriculum mapping did not return a list")
                return None

            # Validate structure
            validated = []
            for item in codes:
                if isinstance(item, dict) and "concept" in item and "curriculum_code" in item:
                    validated.append({
                        "concept": str(item["concept"]),
                        "curriculum_code": str(item["curriculum_code"]),
                        "strand": str(item.get("strand", "")),
                    })

            logger.info(f"Mapped {len(validated)} concepts to curriculum codes for {context}")
            return validated if validated else None

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse curriculum mapping response: {e}")
            return None
        except Exception as e:
            logger.warning(f"Curriculum mapping failed: {e}")
            return None

    @staticmethod
    def to_json_string(codes: list[dict] | None) -> str | None:
        """Serialize curriculum codes to JSON string for database storage."""
        if not codes:
            return None
        return json.dumps(codes)

    @staticmethod
    def from_json_string(json_str: str | None) -> list[dict] | None:
        """Deserialize curriculum codes from JSON string."""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return None
