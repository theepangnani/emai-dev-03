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
# Each template defines the expected output structure
PROMPT_TEMPLATES: dict[str, str] = {
    "teacher_notes": """Based on these teacher notes/handout, create a study guide with this structure:
1. **Summary** — Concise overview of the key topics covered
2. **Key Concepts** — Main ideas and principles explained clearly
3. **Likely Exam Topics** — Topics most likely to appear on tests based on emphasis in the notes
4. **Practice Questions** — 3-5 questions to test understanding of the material""",

    "course_syllabus": """Based on this course syllabus/outline, create a study guide with this structure:
1. **Unit Breakdown** — Each unit/topic with key learning objectives
2. **Study Priority Order** — Rank topics by importance/weight
3. **Weightings** — If marks/weight distribution is mentioned, highlight it
4. **Timeline Checklist** — A chronological study plan based on the syllabus schedule""",

    "past_exam": """Based on this past exam/test, create a study guide with this structure:
1. **Gap Analysis** — Identify which topics were tested and common patterns
2. **Topics Likely Missed** — Based on typical student weaknesses, flag areas that need review
3. **Targeted Drill Questions** — 5-8 practice questions focused on the exam's key topics
4. **Concept Explanations** — Clear explanations of the underlying concepts tested""",

    "mock_exam": """Based on this practice/mock exam, create a study guide with this structure:
1. **Answer Walkthrough** — Step-by-step solutions for each question
2. **Concept Behind Each Question** — Explain what concept each question is testing
3. **Common Mistake Flags** — Warn about typical errors students make on these question types
4. **Similar Practice Problems** — 2-3 additional problems per key concept""",

    "project_brief": """Based on this project brief/assignment rubric, create a study guide with this structure:
1. **Rubric Decoder** — Break down each rubric criterion in plain language
2. **Step-by-Step Plan** — Actionable steps to complete the project
3. **Success Criteria Checklist** — What "excellent" looks like for each criterion
4. **Timeline** — Suggested schedule with milestones working backward from the deadline""",

    "lab_experiment": """Based on this lab/experiment material, create a study guide with this structure:
1. **Pre-Lab Prep** — What to know before starting the lab
2. **Hypothesis Framing** — How to form a proper hypothesis for this experiment
3. **Key Variables** — Independent, dependent, and controlled variables
4. **Report Scaffold** — Template/outline for writing the lab report""",

    "textbook_excerpt": """Based on this textbook excerpt/reading, create a study guide with this structure:
1. **Chapter Summary** — Concise summary of the main ideas
2. **Key Terms** — Important vocabulary with clear definitions
3. **Concept Map** — How the key concepts relate to each other
4. **Review Questions** — 5 questions to test comprehension of the reading""",
}

# Default template when document_type is None or "custom"
DEFAULT_TEMPLATE = """Analyze the content above. If it contains math problems, equations, science calculations, or any exercises/questions that require solving, then:

1. **Worked Solutions** - Solve each problem step-by-step with clear explanations
2. **Key Concepts** - Explain the underlying concepts used in the solutions
3. **Common Mistakes** - Warn about typical errors students make on these types of problems
4. **Practice Problems** - 2-3 similar problems for extra practice (with answers)

If the content is conceptual/reading material (no problems to solve), then:

1. **Key Concepts** - Main topics and ideas to understand
2. **Important Terms** - Vocabulary with definitions
3. **Study Tips** - Strategies for mastering this material
4. **Practice Questions** - 3-5 questions to test understanding
5. **Resources** - Suggested areas to review"""

# Study goal modifiers: appended to the template based on study goal
GOAL_MODIFIERS: dict[str, str] = {
    "upcoming_test": "\n\n**STUDY GOAL: Upcoming Test/Quiz** — Prioritize testable concepts, include practice problems in likely test format, and highlight areas commonly tested.",
    "final_exam": "\n\n**STUDY GOAL: Final Exam** — Cover all major topics comprehensively, create a review checklist, and prioritize high-weight topics.",
    "assignment": "\n\n**STUDY GOAL: Assignment/Project Submission** — Focus on requirements and deliverables, provide step-by-step guidance, and include quality checkpoints.",
    "lab_prep": "\n\n**STUDY GOAL: Lab Preparation** — Emphasize safety procedures, required materials, methodology, and expected outcomes.",
    "general_review": "\n\n**STUDY GOAL: General Review** — Provide a balanced overview of all topics with self-assessment questions.",
    "discussion": "\n\n**STUDY GOAL: Discussion/Presentation** — Highlight key talking points, different perspectives, and supporting evidence.",
    "parent_review": "\n\n**STUDY GOAL: Parent Review** — Use simplified language suitable for a parent helping their child. Explain concepts in plain terms with practical examples of how to support learning at home.",
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
