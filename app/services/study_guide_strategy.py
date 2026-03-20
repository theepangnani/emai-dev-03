"""Study Guide Strategy Pattern Service (§6.105.2, #1974).

Selects prompt templates based on document type, study goal, and focus area.
"""

DOCUMENT_TYPES = [
    "teacher_notes",
    "past_exam",
    "project_brief",
    "lab_experiment",
    "course_syllabus",
    "reading_material",
    "lecture_slides",
    "custom",
]

STUDY_GOALS = [
    "upcoming_test",
    "final_exam",
    "homework_help",
    "general_review",
    "concept_mastery",
]

DEFAULT_TEMPLATE = (
    "Create a comprehensive study guide with these sections:\n"
    "1. Key Concepts — main ideas and definitions\n"
    "2. Summary — concise overview\n"
    "3. Practice — review questions and exercises\n"
    "4. Quick Reference — formulas, dates, key facts"
)

PROMPT_TEMPLATES: dict[str, str] = {
    "teacher_notes": (
        "Analyze these teacher notes and create a study guide:\n"
        "1. Key Concepts — core ideas the teacher emphasized\n"
        "2. Likely Exam Topics — what the teacher will probably test\n"
        "3. Summary — concise overview of the lesson\n"
        "4. Practice Questions — based on teacher emphasis"
    ),
    "past_exam": (
        "Analyze this past exam and create a study guide:\n"
        "1. Gap Analysis — topics tested and difficulty patterns\n"
        "2. Drill Questions — practice problems modeled on the exam\n"
        "3. Common Mistakes — typical errors to avoid\n"
        "4. Study Priority — topics ranked by exam weight"
    ),
    "project_brief": (
        "Analyze this project brief and create a study guide:\n"
        "1. Rubric Decoder — what the teacher expects for top marks\n"
        "2. Step-by-Step Plan — breaking the project into tasks\n"
        "3. Key Requirements — must-have elements\n"
        "4. Research Tips — where to find supporting material"
    ),
    "lab_experiment": (
        "Analyze this lab experiment and create a study guide:\n"
        "1. Pre-Lab Prep — what to review before the lab\n"
        "2. Variables — independent, dependent, and controlled\n"
        "3. Safety Notes — key safety considerations\n"
        "4. Expected Results — what outcomes to anticipate"
    ),
    "course_syllabus": (
        "Analyze this course syllabus and create a study guide:\n"
        "1. Unit Breakdown — key topics per unit\n"
        "2. Assessment Map — tests, projects, and weights\n"
        "3. Key Dates — important deadlines\n"
        "4. Resource List — recommended materials"
    ),
    "reading_material": (
        "Analyze this reading material and create a study guide:\n"
        "1. Key Concepts — main arguments and themes\n"
        "2. Chapter Summaries — concise per-section overview\n"
        "3. Vocabulary — important terms and definitions\n"
        "4. Practice — comprehension questions"
    ),
    "lecture_slides": (
        "Analyze these lecture slides and create a study guide:\n"
        "1. Key Concepts — main ideas from each slide group\n"
        "2. Visual Summaries — diagrams and charts explained\n"
        "3. Fill-in Notes — gaps to complete from memory\n"
        "4. Practice — questions based on slide content"
    ),
}

GOAL_MODIFIERS: dict[str, str] = {
    "upcoming_test": (
        "\n\nSTUDY GOAL: Upcoming Test\n"
        "Focus on likely test questions, memorization aids, and quick-review flashcards."
    ),
    "final_exam": (
        "\n\nSTUDY GOAL: Final Exam Preparation\n"
        "Provide a comprehensive review across all units. Highlight connections between topics."
    ),
    "homework_help": (
        "\n\nSTUDY GOAL: Homework Help\n"
        "Focus on worked examples and step-by-step solutions for practice problems."
    ),
    "general_review": (
        "\n\nSTUDY GOAL: General Review\n"
        "Provide a balanced overview for maintaining knowledge over time."
    ),
    "concept_mastery": (
        "\n\nSTUDY GOAL: Concept Mastery\n"
        "Go deep on explanations, use analogies, and include advanced practice questions."
    ),
}

_SYSTEM_PROMPTS: dict[str, str] = {
    "teacher_notes": (
        "You are a ClassBridge AI study assistant. The student has uploaded teacher notes. "
        "Create a study guide that captures the teacher's emphasis and likely test topics."
    ),
    "past_exam": (
        "You are a ClassBridge AI study assistant. The student has uploaded a past exam. "
        "Analyze the exam structure and create a targeted study guide."
    ),
    "project_brief": (
        "You are a ClassBridge AI study assistant. The student has uploaded a project brief. "
        "Help them decode the requirements and plan their work."
    ),
    "lab_experiment": (
        "You are a ClassBridge AI study assistant. The student has uploaded a lab experiment. "
        "Help them prepare for the lab and understand the science."
    ),
    "course_syllabus": (
        "You are a ClassBridge AI study assistant. The student has uploaded a course syllabus. "
        "Help them plan their semester and identify key milestones."
    ),
    "reading_material": (
        "You are a ClassBridge AI study assistant. The student has uploaded reading material. "
        "Help them extract key ideas and build comprehension."
    ),
    "lecture_slides": (
        "You are a ClassBridge AI study assistant. The student has uploaded lecture slides. "
        "Help them fill in gaps and build complete notes."
    ),
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are a ClassBridge AI study assistant. "
    "Create a clear, well-structured study guide from the provided material."
)


class StudyGuideStrategyService:
    """Selects prompt templates based on document type, study goal, and focus area."""

    @staticmethod
    def get_prompt_template(
        document_type: str | None = None,
        study_goal: str | None = None,
        focus_area: str | None = None,
    ) -> str:
        """Build a prompt template from document type, goal, and focus area."""
        template = PROMPT_TEMPLATES.get(document_type or "", DEFAULT_TEMPLATE)

        if study_goal and study_goal in GOAL_MODIFIERS:
            template += GOAL_MODIFIERS[study_goal]

        if focus_area:
            template += f"\n\nFOCUS AREA: {focus_area}"

        return template

    @staticmethod
    def get_system_prompt(document_type: str | None = None) -> str:
        """Return a system prompt tailored to the document type."""
        if document_type and document_type in _SYSTEM_PROMPTS:
            return _SYSTEM_PROMPTS[document_type]
        return _DEFAULT_SYSTEM_PROMPT
