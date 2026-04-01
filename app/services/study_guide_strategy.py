"""
Study Guide Strategy Pattern Service (§6.105, #1974)

Provides differentiated study guide output structures based on:
- Document Type (what was uploaded)
- Study Goal (what the student is preparing for)
"""
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Document type enum values
DOCUMENT_TYPES = {
    "teacher_notes", "course_syllabus", "past_exam", "mock_exam",
    "project_brief", "lab_experiment", "textbook_excerpt", "custom"
}

# Study goal enum values
STUDY_GOALS = {
    "upcoming_test", "final_exam", "assignment", "lab_prep",
    "general_review", "discussion", "parent_review"
}

# Prompt template map: keyed by document_type
# Each template produces a concise 3-5 sentence overview; detailed content belongs in sub-guides.
PROMPT_TEMPLATES: dict[str, str] = {
    "teacher_notes": """Based on these teacher notes, write a 3-5 sentence summary of what topics are covered and what students should focus on. Do NOT include detailed explanations, formulas, or worked examples — those will be covered in focused sub-guides the student can explore via suggestion chips.""",

    "course_syllabus": """Based on this course syllabus, write a 3-5 sentence summary of the course structure, key units, and what students should prioritize. Do NOT include full unit breakdowns, detailed objectives, or scheduling — those will be covered in focused sub-guides.""",

    "past_exam": """Based on this past exam, write a 3-5 sentence summary identifying the key topics tested and areas students should review. Do NOT reproduce questions or provide solutions — those will be covered in focused sub-guides.""",

    "mock_exam": """Based on this practice/mock exam, write a 3-5 sentence summary of the concepts tested and common pitfalls to watch for. Do NOT include answer walkthroughs or detailed explanations — those will be covered in focused sub-guides.""",

    "project_brief": """Based on this project brief or assignment rubric, write a 3-5 sentence summary of what the project requires and what criteria matter most. Do NOT include step-by-step plans or detailed rubric breakdowns — those will be covered in focused sub-guides.""",

    "lab_experiment": """Based on this lab/experiment material, write a 3-5 sentence summary of the experiment's purpose, key variables, and what students need to prepare. Do NOT include full procedures, safety protocols, or analysis templates — those will be covered in focused sub-guides.""",

    "textbook_excerpt": """Based on this textbook excerpt, write a 3-5 sentence summary of the main ideas and key terms introduced. Do NOT include detailed explanations, definitions, or worked examples — those will be covered in focused sub-guides.""",
}

# Default template when document_type is None or "custom"
DEFAULT_TEMPLATE = """Analyze the content and write a 3-5 sentence summary of what this material covers and what the student should focus on. Do NOT include detailed explanations, worked examples, formulas, or reproduce the source content. Those belong in focused sub-guides the student can explore via suggestion chips."""

# Study goal modifiers: appended to the template based on study goal
GOAL_MODIFIERS: dict[str, str] = {
    "upcoming_test": "\n\n**STUDY GOAL: Upcoming Test/Quiz** — Emphasize testable concepts and likely test areas.",
    "final_exam": "\n\n**STUDY GOAL: Final Exam** — Prioritize high-weight topics across all units.",
    "assignment": "\n\n**STUDY GOAL: Assignment/Project** — Focus on requirements and key deliverables.",
    "lab_prep": "\n\n**STUDY GOAL: Lab Preparation** — Emphasize safety, materials, and methodology.",
    "general_review": "\n\n**STUDY GOAL: General Review** — Provide a balanced overview of all topics.",
    "discussion": "\n\n**STUDY GOAL: Discussion/Presentation** — Highlight key talking points and perspectives.",
    "parent_review": "\n\n**STUDY GOAL: Parent Review** — Use simplified language suitable for a parent helping their child.",
}


class StudyGuideStrategyService:
    """Service that selects and builds AI prompts based on document type and study goal."""

    @staticmethod
    def get_prompt_template(
        document_type: str | None = None,
        study_goal: str | None = None,
        focus_area: str | None = None,
    ) -> str:
        """
        Build the appropriate prompt section based on document type and study goal.

        Args:
            document_type: The classified document type (e.g., "teacher_notes", "past_exam")
            study_goal: The student's study goal (e.g., "upcoming_test", "final_exam")
            focus_area: Optional free-form focus text from the student

        Returns:
            Prompt instruction string to inject into the AI generation prompt
        """
        # Select base template
        if document_type and document_type in PROMPT_TEMPLATES:
            template = PROMPT_TEMPLATES[document_type]
            logger.info(f"Using strategy template for document_type={document_type}")
        else:
            template = DEFAULT_TEMPLATE
            if document_type:
                logger.info(f"No specific template for document_type={document_type}, using default")

        # Apply study goal modifier
        if study_goal and study_goal in GOAL_MODIFIERS:
            template += GOAL_MODIFIERS[study_goal]
            logger.info(f"Applied study goal modifier: {study_goal}")

        # Apply focus area
        if focus_area:
            template += f"\n\n**FOCUS AREA:** The student wants to focus specifically on: {focus_area}. Prioritize these topics in your response while still covering other key material briefly."

        return template

    @staticmethod
    def get_system_prompt(document_type: str | None = None) -> str:
        """
        Get the appropriate system prompt based on document type.

        Args:
            document_type: The classified document type

        Returns:
            System prompt string for the AI model
        """
        base = "You are an expert educational tutor on a K-12 education platform called ClassBridge."

        type_contexts = {
            "teacher_notes": " You are analyzing teacher-created notes and handouts to create study materials.",
            "course_syllabus": " You are analyzing a course syllabus to help students plan their study strategy.",
            "past_exam": " You are analyzing a past exam to help students identify knowledge gaps and prepare effectively.",
            "mock_exam": " You are analyzing a practice exam to provide detailed answer walkthroughs and concept explanations.",
            "project_brief": " You are analyzing a project brief to help students plan and execute their assignment.",
            "lab_experiment": " You are analyzing lab/experiment materials to help students prepare for and report on their lab work.",
            "textbook_excerpt": " You are analyzing textbook content to create a comprehensive study summary.",
        }

        if document_type and document_type in type_contexts:
            base += type_contexts[document_type]
        else:
            base += " When given math problems or exercises, solve them step-by-step with clear explanations. For conceptual material, create well-organized study guides."

        base += " Use simple language, practical examples, and clean Markdown formatting. For math, use LaTeX notation with $...$ for inline and $$...$$ for display equations."

        return base
