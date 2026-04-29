"""
Parent Companion Generation Service (CB-CMCP-001 M1-F 1F-1, #4463).

Initial port of phase-2 ParentSummaryService (`c:/dev/emai/class-bridge-phase-2/
app/services/parent_summary.py`, 116 LOC). Ports the existing service as-is —
the 5-section structure extension (FR-02.6) ships in 1F-2 wave 2.

Generates a parent-facing simplified summary alongside every student study guide.
This is ClassBridge's unique "Parent Visibility Layer" differentiator.

Example output:
"Haashini is preparing for a Grade 8 science lab on cell division.
Here are 3 ways you can support her tonight:
1. Ask her to explain the difference between mitosis and meiosis
2. Help her review the key vocabulary terms highlighted in yellow
3. Quiz her on the practice questions at the end of the study guide"
"""
from app.core.logging_config import get_logger
from app.services.ai_service import generate_content

logger = get_logger(__name__)

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
