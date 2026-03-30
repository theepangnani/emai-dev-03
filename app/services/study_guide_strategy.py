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
# Each template defines the expected output structure (overview-first: concise bullet points)
PROMPT_TEMPLATES: dict[str, str] = {
    "teacher_notes": """Based on these teacher notes/handout, create a brief study guide overview:
1. **Summary of Key Topics** — Brief bullet-point overview of the main topics covered
2. **Likely Exam Areas** — Bullet points of topics most likely to appear on tests""",

    "course_syllabus": """Based on this course syllabus/outline, create a brief study guide overview:
1. **Unit Overview** — Bullet-point list of each unit/topic with key objectives
2. **Study Priorities** — Top topics ranked by importance/weight""",

    "past_exam": """Based on this past exam/test, create a brief study guide overview:
1. **Key Gap Areas** — Bullet points of topics tested and common patterns
2. **Topics to Review** — Brief list of areas that likely need attention""",

    "mock_exam": """Based on this practice/mock exam, create a brief study guide overview:
1. **Key Concepts Tested** — Bullet-point list of what each question tests
2. **Common Pitfalls** — Brief list of typical mistakes to watch for""",

    "project_brief": """Based on this project brief/assignment rubric, create a brief study guide overview:
1. **Requirements Summary** — Bullet points of each rubric criterion in plain language
2. **Key Deliverables** — Brief list of what needs to be completed""",

    "lab_experiment": """Based on this lab/experiment material, create a brief study guide overview:
1. **Pre-Lab Essentials** — Bullet points of what to know before starting
2. **Key Variables** — Brief list of independent, dependent, and controlled variables""",

    "textbook_excerpt": """Based on this textbook excerpt/reading, create a brief study guide overview:
1. **Main Ideas** — Bullet-point summary of the key concepts
2. **Key Terms** — Brief list of important vocabulary""",
}

# Default template when document_type is None or "custom"
DEFAULT_TEMPLATE = """Analyze the content above and create a brief study guide overview:

If it contains math problems, equations, or exercises that require solving:
1. **Key Concepts** — Bullet points of the underlying concepts involved
2. **Problem Types** — Brief list of the types of problems present

If the content is conceptual/reading material:
1. **Key Concepts** — Bullet-point overview of main topics and ideas
2. **Important Terms** — Brief list of key vocabulary"""

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
