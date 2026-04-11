"""
Study Guide Strategy Pattern Service (§6.105, #1974)

Provides differentiated study guide output structures based on:
- Document Type (what was uploaded)
- Study Goal (what the student is preparing for)
- Detected Subject (math, science, english, french)
- Requested Output (study_guide, worksheet, high_level_summary)
"""
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Document type enum values
# NOTE (G6 #3024): "teacher_notes" covers both teacher handouts and class notes.
# The PRD originally had two separate chip sets for these, but since the AI cannot
# reliably distinguish "teacher handout" from "class notes" under the same enum value,
# they are merged into the single "teacher_notes" chip set. The template resolver
# maps teacher_notes to one consistent template regardless of sub-type.
DOCUMENT_TYPES = {
    "teacher_notes", "course_syllabus", "past_exam", "mock_exam",
    "project_brief", "lab_experiment", "textbook_excerpt", "custom",
    "parent_question", "worksheet", "student_test", "quiz_paper",
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

    "worksheet": """Based on this worksheet, write a 3-5 sentence summary of the topics and skills being practiced. Do NOT reproduce individual questions or provide answers — those will be covered in focused sub-guides the student can explore via suggestion chips.""",

    "student_test": """Based on this completed/marked test, write a 3-5 sentence summary identifying the topics tested, areas of strength, and areas where the student lost marks. Do NOT reproduce questions or rework solutions — those will be covered in focused sub-guides.""",

    "quiz_paper": """Based on this quiz paper, write a 3-5 sentence summary of the topics and question types covered. Do NOT reproduce questions or provide answers — those will be covered in focused sub-guides the student can explore via suggestion chips.""",

    "parent_question": """The content below is an open-ended question from a parent about their child's education. Do NOT summarize source material — there is none. Instead, ANSWER the question directly and create a COMPREHENSIVE, DETAILED study preparation guide.

This is a FULL study guide, not a brief overview. Write a thorough, actionable response that includes:

1. **Understanding the Challenge** — What the student is facing (assessment format, curriculum expectations, what's being tested)
2. **Step-by-Step Preparation Plan** — 4-6 concrete, numbered strategies the parent can use with their child
3. **Key Focus Areas** — Specific topics, skills, or sections to prioritize
4. **Recommended Resources** — Official resources (e.g., eqao.com for OSSLT practice tests), prep books, or free online tools where applicable
5. **Test Day Tips** — Practical advice for the day of (if applicable)
6. **Accommodations & Support** — IEP, extra time, school resources the parent should ask about (if relevant)

Use Ontario K-12 curriculum context where applicable (OSSLT, EQAO, grade-level expectations, school board specifics).
Use Markdown formatting with clear headings (##), bullet points, and bold for emphasis.
Use encouraging, supportive tone appropriate for a parent audience.
Do NOT say "based on the source material" — the parent asked a question and you are providing expert educational guidance.

SAFETY: Only provide age-appropriate, educationally relevant content. Do NOT provide advice on topics unrelated to education, academics, or student wellbeing. If the question is off-topic, politely redirect to educational guidance.""",
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


# ── Template Prompts Registry (S3 #2951) ──────────────────────────────────
# Maps each named template key (returned by resolve_template_key) to its prompt.
TEMPLATE_PROMPTS: dict[str, str] = {
    "study_guide_overview": DEFAULT_TEMPLATE,

    "study_guide_math": """Based on this math content, create a study guide that emphasizes:
- Key formulas and equations (use LaTeX: $...$ inline, $$...$$ display)
- Step-by-step worked solutions for representative problems
- Common mistakes and how to avoid them
- Practice problem types students should expect
Write clearly and show all intermediate steps.""",

    "study_guide_science": """Based on this science content, create a study guide that emphasizes:
- Core scientific concepts and definitions
- Diagrams and visual descriptions (describe what a diagram would show)
- Lab methodology: hypothesis → procedure → observation → conclusion
- Key formulas with units and dimensional analysis
- Cause-and-effect relationships between concepts""",

    "study_guide_english": """Based on this English/French language arts content, create a study guide that emphasizes:
- Reading comprehension strategies and key themes
- Writing structure: thesis, evidence, analysis
- Grammar and syntax rules with examples
- Vocabulary in context
- Literary devices and techniques used in the text""",

    "worksheet_general": """Based on this content, create a worksheet with exactly 10 questions:
- Mix question types: multiple choice, short answer, and one extended response
- Questions should directly test the key concepts from the source material
- Order from easiest to hardest
- Leave space indicators (e.g., "[Space for answer]") after each question
- Include an answer key at the end""",

    "worksheet_math_word_problems": """Based on this math content, create a worksheet of 10 real-world word problems:
- Each problem should apply a concept from the source material to a realistic scenario
- Number problems clearly (1-10), ordered from easiest to hardest
- After each problem, include "[Show your work here]" space
- Use age-appropriate contexts (school, sports, shopping, cooking)
- Include an answer key at the end with step-by-step solutions""",

    "worksheet_english": """Based on this English content, create a worksheet with:
- 3 grammar exercises (identify/correct errors, fill in blanks)
- 3 reading comprehension questions (reference specific passages)
- 2 short writing prompts (1 paragraph each)
- 2 vocabulary-in-context questions
- Include an answer key at the end""",

    "worksheet_french": """Based on this French content, create a worksheet with:
- 3 grammar exercises (conjugation, accord, structure de phrase)
- 3 comprehension questions in French (référence au texte)
- 2 short writing prompts in French (1 paragraphe chacun)
- 2 vocabulary exercises (synonymes, antonymes, ou contexte)
- Include an answer key (corrigé) at the end
Write all instructions in French.""",

    "high_level_summary": """Provide a concise high-level summary of this content in 3-5 bullet points.
- Each bullet should capture one key idea or takeaway
- Use simple, clear language a parent or student can scan quickly
- Do NOT include detailed explanations, formulas, or worked examples
- Keep the entire response under 200 words""",
}


def resolve_template_key(
    detected_subject: str,
    requested_output: str = "study_guide",
) -> str:
    """
    Resolve the appropriate template key based on detected subject
    and requested output type.

    Args:
        detected_subject: The detected subject area (e.g., "math", "science", "english", "french")
        requested_output: The type of output requested ("study_guide", "worksheet", "high_level_summary")

    Returns:
        A key into TEMPLATE_PROMPTS
    """
    if requested_output == "high_level_summary":
        return "high_level_summary"

    if requested_output == "worksheet":
        if detected_subject == "math":
            return "worksheet_math_word_problems"
        if detected_subject == "english":
            return "worksheet_english"
        if detected_subject == "french":
            return "worksheet_french"
        return "worksheet_general"

    # Default: study_guide
    if detected_subject == "math":
        return "study_guide_math"
    if detected_subject == "science":
        return "study_guide_science"
    if detected_subject in ("english", "french"):
        return "study_guide_english"
    return "study_guide_overview"
# Subjects that route to generic templates (no subject-specific customization)
GENERIC_SUBJECTS = {"mixed", "unknown", None}

# Worksheet prompt templates (#2956) — moved from study.py (S1)
WORKSHEET_PROMPT_TEMPLATES = {
    "worksheet_general": (
        "Create a worksheet with {num_questions} mixed questions based on the following material. "
        "Number each question clearly and add answer blanks or space for student responses."
    ),
    "worksheet_math_word_problems": (
        "Create a worksheet with {num_questions} real-world word problems based on the following material. "
        "Include step-by-step working space for each problem. Use LaTeX notation ($$...$$) for mathematical formulas."
    ),
    "worksheet_english": (
        "Create a worksheet with {num_questions} English exercises based on the following material. "
        "Include a mix of grammar, reading comprehension, and short writing prompts."
    ),
    "worksheet_french": (
        "Create a worksheet with {num_questions} French exercises based on the following material. "
        "Include a mix of vocabulary, verb conjugation, and translation exercises."
    ),
}

DIFFICULTY_LABELS = {
    "below_grade": "slightly below grade level (easier, more scaffolding)",
    "grade_level": "at grade level",
    "above_grade": "above grade level (more challenging, extension-level)",
}


class StudyGuideStrategyService:
    """Service that selects and builds AI prompts based on document type and study goal."""

    @staticmethod
    def get_prompt_template(
        document_type: str | None = None,
        study_goal: str | None = None,
        focus_area: str | None = None,
        template_key: str | None = None,
        detected_subject: str | None = None,
    ) -> str:
        """
        Build the appropriate prompt section based on document type and study goal.

        The template_key (from resolve_template_key) selects the base template from
        TEMPLATE_PROMPTS. GOAL_MODIFIERS are still layered on top (G7 #3025).

        Args:
            document_type: The classified document type (e.g., "teacher_notes", "past_exam")
            study_goal: The student's study goal (e.g., "upcoming_test", "final_exam")
            focus_area: Optional free-form focus text from the student
            template_key: Optional key into TEMPLATE_PROMPTS (from resolve_template_key)
            detected_subject: The detected academic subject (e.g., "math", "science", "mixed")

        Returns:
            Prompt instruction string to inject into the AI generation prompt
        """
        # Select base template — prefer template_key if provided
        if template_key and template_key in TEMPLATE_PROMPTS:
            template = TEMPLATE_PROMPTS[template_key]
            logger.info(f"Using named template: template_key={template_key}")
        elif document_type and document_type in PROMPT_TEMPLATES:
            template = PROMPT_TEMPLATES[document_type]
            logger.info(f"Using strategy template for document_type={document_type}")
        else:
            template = DEFAULT_TEMPLATE
            if document_type:
                logger.info(f"No specific template for document_type={document_type}, using default")

        # Apply study goal modifier (G7: always layer on top of template key)
        if study_goal and study_goal in GOAL_MODIFIERS:
            template += GOAL_MODIFIERS[study_goal]
            logger.info(f"Applied study goal modifier: {study_goal}")

        # Apply focus area
        if focus_area:
            template += f"\n\n**FOCUS AREA:** The student wants to focus specifically on: {focus_area}. Prioritize these topics in your response while still covering other key material briefly."

        # Apply subject context (generic subjects like 'mixed'/'unknown' use the default template with no subject modifier)
        if detected_subject and detected_subject not in GENERIC_SUBJECTS:
            template += f"\n\n**SUBJECT:** This material is for {detected_subject.replace('_', ' ')}. Tailor terminology, examples, and study strategies to this subject area."
            logger.info(f"Applied subject context: {detected_subject}")

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
            "parent_question": " A parent has asked an open-ended question about their child's education. You are providing expert guidance, study strategies, and actionable advice. You have deep knowledge of Ontario K-12 curriculum, standardized assessments (OSSLT, EQAO), and evidence-based study techniques. Only provide age-appropriate, educationally relevant content. Never provide medical, legal, or mental health advice — suggest consulting appropriate professionals if needed.",
        }

        if document_type and document_type in type_contexts:
            base += type_contexts[document_type]
        else:
            base += " When given math problems or exercises, solve them step-by-step with clear explanations. For conceptual material, create well-organized study guides."

        base += " Use simple language, practical examples, and clean Markdown formatting. For math, use LaTeX notation with $...$ for inline and $$...$$ for display equations."

        return base
