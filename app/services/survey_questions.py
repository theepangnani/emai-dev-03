"""Static survey question definitions for pre-launch market research."""

from typing import Any

SURVEY_QUESTIONS: dict[str, list[dict]] = {
    "parent": [
        {
            "key": "P1",
            "text": "How do you currently help your child with schoolwork?",
            "type": "multi_select",
            "required": True,
            "options": [
                "Review homework together",
                "Hire a private tutor",
                "Use online learning platforms (Khan Academy, etc.)",
                "Use AI tools (ChatGPT, etc.)",
                "Check school portals (Google Classroom, TeachAssist, etc.)",
                "I don't actively help — my child is independent",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "P2",
            "text": "How would you describe your involvement in your child's education?",
            "type": "single_select",
            "required": True,
            "options": [
                "Hands-on Guide — I actively review work, set study schedules, and stay in close contact with teachers",
                "Structured Director — I set clear rules and expectations, and monitor progress closely",
                "Supportive Observer — I'm available when needed but let my child take the lead",
                "Independent Encourager — I trust my child to manage their own learning with minimal oversight",
                "Balanced Partner — I adjust my involvement based on my child's needs at the time",
            ],
        },
        {
            "key": "P3",
            "text": "What are your biggest challenges in supporting your child's education?",
            "type": "multi_select",
            "required": True,
            "options": [
                "Hard to keep track of assignments and due dates across multiple platforms",
                "Don't understand the material well enough to help",
                "Limited time due to work/other commitments",
                "Hard to communicate with teachers",
                "My child doesn't share school information with me",
                "Too many apps/portals to check",
                "Not sure how to help effectively",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "P4",
            "text": "Which AI or learning tools have you or your child used?",
            "type": "multi_select",
            "required": True,
            "options": [
                "ChatGPT / OpenAI",
                "Google Gemini",
                "Microsoft Copilot",
                "Khan Academy",
                "Quizlet",
                "Photomath",
                "Grammarly",
                "None",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "P5",
            "text": "How comfortable are you with AI tools being used for education?",
            "type": "likert",
            "required": True,
            "likert_min_label": "Not comfortable at all",
            "likert_max_label": "Very comfortable",
        },
        {
            "key": "P6",
            "text": "How useful would the following features be to you?",
            "type": "likert_matrix",
            "required": True,
            "sub_items": [
                "See all your child's assignments, grades, and deadlines in one dashboard",
                "Get a daily summary of what your child needs to work on",
                "AI-generated study guides from class materials",
                "Direct messaging with your child's teachers",
                "Track your child's study progress and time spent",
                "AI tutor that helps your child with homework step-by-step",
                "Manage all course materials (notes, files, resources) in one place",
                "Weekly progress report emailed to you",
            ],
            "likert_min_label": "Not useful",
            "likert_max_label": "Very useful",
        },
        {
            "key": "P7",
            "text": "How would you feel about having all your children's study materials organized in one platform?",
            "type": "likert",
            "required": True,
            "likert_min_label": "Not interested",
            "likert_max_label": "Would love this",
        },
        {
            "key": "P8",
            "text": "Would you subscribe to an app that helps you stay connected with your child's education, manage their tasks/assignments, and provide AI-powered tutoring?",
            "type": "single_select",
            "required": True,
            "options": [
                "Yes, definitely",
                "Probably yes",
                "Maybe, depends on price",
                "Probably not",
                "No",
            ],
        },
        {
            "key": "P9",
            "text": "What would you be willing to pay monthly for such a service?",
            "type": "single_select",
            "required": True,
            "options": [
                "Free only",
                "$1–$5/month",
                "$5–$10/month",
                "$10–$20/month",
                "$20+/month",
            ],
        },
        {
            "key": "P10",
            "text": "Any other comments, suggestions, or features you'd like to see?",
            "type": "free_text",
            "required": False,
        },
    ],
    "student": [
        {
            "key": "S1",
            "text": "How do you currently organize your school materials (notes, assignments, study resources)?",
            "type": "multi_select",
            "required": True,
            "options": [
                "Google Classroom / school portal",
                "Paper notebooks and folders",
                "Notes app on my phone/computer",
                "Cloud storage (Google Drive, OneDrive)",
                "I don't really organize them",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "S2",
            "text": "How much time do you spend daily downloading, organizing, and uploading class materials?",
            "type": "single_select",
            "required": True,
            "options": [
                "Less than 5 minutes",
                "5–15 minutes",
                "15–30 minutes",
                "More than 30 minutes",
                "I don't do this at all",
            ],
        },
        {
            "key": "S3",
            "text": "How comfortable would you be spending 15 minutes daily to keep your study materials organized if it meant better grades?",
            "type": "likert",
            "required": True,
            "likert_min_label": "Not willing",
            "likert_max_label": "Definitely willing",
        },
        {
            "key": "S4",
            "text": "Which AI or learning tools do you use for studying?",
            "type": "multi_select",
            "required": True,
            "options": [
                "ChatGPT / OpenAI",
                "Google Gemini",
                "Microsoft Copilot",
                "Khan Academy",
                "Quizlet",
                "Photomath",
                "Grammarly",
                "YouTube tutorials",
                "None",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "S5",
            "text": "How useful would the following features be to you?",
            "type": "likert_matrix",
            "required": True,
            "sub_items": [
                "AI that generates study guides from your class notes and textbooks",
                "Flashcards and quizzes auto-created from your materials",
                "One place to see all assignments and deadlines across classes",
                "AI tutor you can chat with about any subject",
                "Share study materials with classmates",
                "Track your study time and progress",
                "Get reminders about upcoming tests and due dates",
            ],
            "likert_min_label": "Not useful",
            "likert_max_label": "Very useful",
        },
        {
            "key": "S6",
            "text": "Would you use an app that organizes all your school materials in one place and helps you study with AI?",
            "type": "single_select",
            "required": True,
            "options": [
                "Yes, definitely",
                "Probably yes",
                "Maybe",
                "Probably not",
                "No",
            ],
        },
        {
            "key": "S7",
            "text": "How would you feel about your parent/guardian being able to see your assignment deadlines and study progress?",
            "type": "single_select",
            "required": True,
            "options": [
                "Totally fine with it",
                "Okay if I can control what they see",
                "Neutral",
                "Prefer they don't",
                "Absolutely not",
            ],
        },
        {
            "key": "S8",
            "text": "Any other comments, suggestions, or features you'd like to see?",
            "type": "free_text",
            "required": False,
        },
    ],
    "teacher": [
        {
            "key": "T1",
            "text": "Which platforms do you currently use for teaching and class management?",
            "type": "multi_select",
            "required": True,
            "options": [
                "Google Classroom",
                "Microsoft Teams / OneNote",
                "Canvas",
                "Brightspace (D2L)",
                "Schoology",
                "Edmodo",
                "Paper-based only",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "T2",
            "text": "What are your biggest challenges with your current teaching tools?",
            "type": "multi_select",
            "required": True,
            "options": [
                "Hard to communicate with parents",
                "Students don't check or use the platform",
                "Difficult to track individual student progress",
                "Too many disconnected tools",
                "Limited AI/smart features",
                "Time-consuming to create study materials",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "T3",
            "text": "Which AI tools do you use in your teaching?",
            "type": "multi_select",
            "required": True,
            "options": [
                "ChatGPT / OpenAI",
                "Google Gemini",
                "Microsoft Copilot",
                "AI lesson plan generators",
                "AI grading assistants",
                "None",
                "Other",
            ],
            "allow_other": True,
        },
        {
            "key": "T4",
            "text": "How comfortable are you with students using AI tools for learning?",
            "type": "likert",
            "required": True,
            "likert_min_label": "Not comfortable at all",
            "likert_max_label": "Very comfortable",
        },
        {
            "key": "T5",
            "text": "How useful would the following features be in a teaching platform?",
            "type": "likert_matrix",
            "required": True,
            "sub_items": [
                "AI that generates study guides from your uploaded course materials",
                "Automatic quiz and flashcard creation from lesson content",
                "Built-in parent-teacher messaging",
                "Dashboard showing each student's engagement and progress",
                "Parents can see assignment deadlines and help at home",
                "AI tutor for students that works from your actual course materials",
                "One platform that syncs with Google Classroom",
            ],
            "likert_min_label": "Not useful",
            "likert_max_label": "Very useful",
        },
        {
            "key": "T6",
            "text": "How would you feel about parents having visibility into assignment deadlines and their child's progress through a shared platform?",
            "type": "single_select",
            "required": True,
            "options": [
                "Great idea — would improve parent engagement",
                "Okay if I can control what is shared",
                "Neutral",
                "Concerned about privacy",
                "Against it",
            ],
        },
        {
            "key": "T7",
            "text": "Would you recommend a platform like this to your school or department?",
            "type": "single_select",
            "required": True,
            "options": [
                "Yes, definitely",
                "Probably yes",
                "Maybe",
                "Probably not",
                "No",
            ],
        },
        {
            "key": "T8",
            "text": "Do you also do private tutoring outside of school?",
            "type": "single_select",
            "required": True,
            "options": [
                "Yes, regularly",
                "Occasionally",
                "No, but I'm interested",
                "No",
            ],
        },
        {
            "key": "T9",
            "text": "Any other comments, suggestions, or features you'd like to see?",
            "type": "free_text",
            "required": False,
        },
    ],
}

VALID_SURVEY_ROLES = {"parent", "student", "teacher"}


def get_questions_for_role(role: str) -> list[dict] | None:
    """Return question definitions for a role, or None if invalid."""
    return SURVEY_QUESTIONS.get(role)


def get_question_map_for_role(role: str) -> dict[str, dict] | None:
    """Return a dict mapping question_key -> question for a role."""
    questions = SURVEY_QUESTIONS.get(role)
    if questions is None:
        return None
    return {q["key"]: q for q in questions}


def validate_answer(question: dict, answer_value: Any) -> bool:
    """Validate an answer value against its question type."""
    q_type = question["type"]

    if q_type == "single_select":
        return isinstance(answer_value, str) and answer_value in question.get("options", [])

    if q_type == "multi_select":
        if not isinstance(answer_value, list):
            return False
        options = set(question.get("options", []))
        allow_other = question.get("allow_other", False)
        for item in answer_value:
            if not isinstance(item, str):
                return False
            if item not in options and not allow_other:
                return False
        return len(answer_value) > 0

    if q_type == "likert":
        return isinstance(answer_value, int) and 1 <= answer_value <= 5

    if q_type == "likert_matrix":
        if not isinstance(answer_value, dict):
            return False
        sub_items = set(question.get("sub_items", []))
        for key, val in answer_value.items():
            if key not in sub_items:
                return False
            if not isinstance(val, int) or not (1 <= val <= 5):
                return False
        return len(answer_value) == len(sub_items)

    if q_type == "free_text":
        return isinstance(answer_value, str)

    return False
