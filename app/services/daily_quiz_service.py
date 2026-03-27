"""
Daily Quiz ("Quiz of the Day") service — #2225.

Generates a 5-question quiz per student per day based on their recent study
materials (last 7 days).  Falls back to a general-knowledge quiz matched to
the student's grade level when no recent materials exist.
"""
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.daily_quiz import DailyQuiz
from app.models.study_guide import StudyGuide
from app.models.student import Student
from app.models.user import User

logger = get_logger(__name__)

NUM_QUESTIONS = 5


def _get_recent_material_context(db: Session, user_id: int) -> str | None:
    """Gather text snippets from the student's last-7-day study guides."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    guides = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == user_id,
            StudyGuide.created_at >= cutoff,
            StudyGuide.archived_at.is_(None),
        )
        .order_by(StudyGuide.created_at.desc())
        .limit(10)
        .all()
    )
    if not guides:
        return None

    snippets: list[str] = []
    for g in guides:
        # For quizzes/flashcards the content is JSON; for study_guide it's markdown
        if g.guide_type == "quiz":
            try:
                questions = json.loads(g.content)
                for q in questions[:3]:
                    snippets.append(q.get("question", ""))
            except Exception:
                pass
        else:
            snippets.append(g.content[:500])
    return "\n---\n".join(snippets)[:3000]


def _get_grade_level(db: Session, user_id: int) -> int | None:
    """Return the student's grade level if available."""
    student = db.query(Student).filter(Student.user_id == user_id).first()
    return student.grade_level if student else None


def _build_prompt(context: str | None, grade_level: int | None) -> str:
    """Build the AI prompt for quiz generation."""
    if context:
        return (
            f"Based on the following study material excerpts, generate a Quiz of the Day "
            f"with exactly {NUM_QUESTIONS} multiple-choice questions. Each question should "
            f"test understanding of the material. Mix easy and medium difficulty.\n\n"
            f"Study material:\n{context}\n\n"
            f"Return ONLY a JSON array of {NUM_QUESTIONS} objects, each with keys: "
            f'"question", "options" (object with keys A, B, C, D), "correct_answer" '
            f'(one of A/B/C/D), "explanation".'
        )

    grade_str = f"grade {grade_level}" if grade_level else "a middle-school student"
    return (
        f"Generate a fun, educational Quiz of the Day with exactly {NUM_QUESTIONS} "
        f"multiple-choice general knowledge questions appropriate for {grade_str}. "
        f"Cover a mix of subjects: math, science, history, geography, and language arts. "
        f"Each question should be engaging and educational.\n\n"
        f"Return ONLY a JSON array of {NUM_QUESTIONS} objects, each with keys: "
        f'"question", "options" (object with keys A, B, C, D), "correct_answer" '
        f'(one of A/B/C/D), "explanation".'
    )


async def _generate_quiz_questions(context: str | None, grade_level: int | None) -> list[dict]:
    """Call AI to generate quiz questions."""
    from app.services.ai_service import generate_content

    prompt = _build_prompt(context, grade_level)
    system_prompt = (
        "You are a quiz generator for a K-12 educational platform. "
        "Generate engaging, age-appropriate multiple-choice questions. "
        "Return ONLY valid JSON — no markdown fences, no extra text."
    )

    content, _ = await generate_content(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=1500,
        temperature=0.8,
    )

    # Parse JSON from response — handle markdown fences
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    questions = json.loads(text)
    if not isinstance(questions, list):
        raise ValueError("Expected JSON array of questions")

    # Validate and trim to NUM_QUESTIONS
    validated: list[dict] = []
    for q in questions[:NUM_QUESTIONS]:
        if all(k in q for k in ("question", "options", "correct_answer", "explanation")):
            validated.append({
                "question": q["question"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "explanation": q["explanation"],
            })

    if len(validated) < NUM_QUESTIONS:
        raise ValueError(f"Only {len(validated)} valid questions generated")

    return validated


def get_daily_quiz(db: Session, user: User) -> DailyQuiz | None:
    """Return today's cached daily quiz for the user, or None if not yet generated."""
    today = date.today()
    return (
        db.query(DailyQuiz)
        .filter(DailyQuiz.user_id == user.id, DailyQuiz.quiz_date == today)
        .first()
    )


async def get_or_create_daily_quiz(db: Session, user: User) -> DailyQuiz:
    """Return today's quiz, generating via AI if needed."""
    existing = get_daily_quiz(db, user)
    if existing:
        return existing

    # Determine target user for material lookup
    # For parents, we look up their first linked child's materials
    target_user_id = user.id
    from app.models.student import parent_students
    if user.role and user.role.value == "parent":
        row = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == user.id
        ).first()
        if row:
            child_student = db.query(Student).filter(Student.id == row[0]).first()
            if child_student:
                target_user_id = child_student.user_id

    context = _get_recent_material_context(db, target_user_id)
    grade_level = _get_grade_level(db, target_user_id)

    questions = await _generate_quiz_questions(context, grade_level)

    quiz = DailyQuiz(
        user_id=user.id,
        quiz_date=date.today(),
        questions_json=json.dumps(questions),
        title=f"Daily Challenge: {date.today().strftime('%B %d, %Y')}",
        total_questions=len(questions),
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    logger.info(
        "Daily quiz generated | user_id=%s | date=%s | from_materials=%s",
        user.id, date.today(), context is not None,
    )
    return quiz


def submit_daily_quiz(db: Session, user: User, answers: dict[int, str]) -> dict:
    """Score the daily quiz and return results. Awards XP if system is enabled."""
    quiz = get_daily_quiz(db, user)
    if not quiz:
        raise ValueError("No daily quiz found for today")
    if quiz.completed_at is not None:
        raise ValueError("Daily quiz already completed")

    questions = json.loads(quiz.questions_json)
    score = 0
    for i, q in enumerate(questions):
        if answers.get(i) == q["correct_answer"]:
            score += 1

    percentage = round((score / len(questions)) * 100, 1) if questions else 0.0

    quiz.score = score
    quiz.percentage = percentage
    quiz.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Award XP (non-blocking)
    xp_awarded = None
    try:
        from app.services.xp_service import XpService
        entry = XpService.award_xp(db, user.id, "quiz_complete", context_id=f"daily_{quiz.id}")
        if entry:
            xp_awarded = entry.xp_awarded
    except Exception as e:
        logger.warning("XP award failed for daily quiz (non-blocking): %s", e)

    return {
        "score": score,
        "total_questions": len(questions),
        "percentage": percentage,
        "xp_awarded": xp_awarded,
    }
