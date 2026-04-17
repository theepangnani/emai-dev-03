"""ASGF auto-save service — persist completed sessions as Class Material (#3401)."""
import json

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.learning_history import LearningHistory
from app.models.study_guide import StudyGuide
from app.services.ai_service import get_async_anthropic_client
from app.services.asgf_learning_history_service import update_learning_history_on_complete

logger = get_logger(__name__)


def _render_slides_as_markdown(slides: list[dict]) -> str:
    """Convert slide dicts into readable markdown content."""
    parts: list[str] = []
    for i, slide in enumerate(slides, 1):
        title = slide.get("title", f"Slide {i}")
        body = slide.get("body", slide.get("content", ""))
        parts.append(f"## {title}\n\n{body}")
        vocab = slide.get("vocabulary_terms", [])
        if vocab:
            parts.append("\n**Key Terms:** " + ", ".join(vocab))
    return "\n\n---\n\n".join(parts)


def _render_quiz_markdown(quiz_results: list[dict]) -> str:
    """Render quiz results as a markdown section."""
    lines = ["## Quiz Results\n"]
    correct_count = sum(1 for q in quiz_results if q.get("correct"))
    total = len(quiz_results)
    lines.append(f"**Score: {correct_count}/{total}**\n")
    for i, q in enumerate(quiz_results, 1):
        status = "Correct" if q.get("correct") else "Incorrect"
        attempts = q.get("attempts", 1)
        lines.append(f"{i}. {q.get('question_text', 'Question')} — {status} ({attempts} attempt{'s' if attempts != 1 else ''})")
    return "\n".join(lines)


async def _generate_summary(
    question: str,
    student_name: str,
    correct_count: int,
    total_count: int,
    subject: str,
) -> str:
    """Generate a 1-2 sentence AI summary of the session using Claude Haiku."""
    prompt = (
        f"Write exactly 1-2 sentences summarising this study session for a parent.\n"
        f"Student: {student_name}\n"
        f"Question studied: {question}\n"
        f"Subject: {subject}\n"
        f"Quiz score: {correct_count}/{total_count}\n\n"
        f"Example: \"{student_name} completed a Flash Study on Newton's Third Law. "
        f"She answered 4 of 5 correctly.\"\n\n"
        f"Return ONLY the summary text, no quotes or extra formatting."
    )
    try:
        client = get_async_anthropic_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.content[0].text.strip()
    except Exception:
        logger.warning("ASGF auto-save: summary generation failed, using fallback")
        return (
            f"{student_name} completed a Flash Study on {subject}. "
            f"Score: {correct_count}/{total_count}."
        )


async def auto_save_session(
    session_id: str,
    slides: list[dict],
    quiz_results: list[dict],
    student_id: int,
    db: Session,
) -> tuple[int, str]:
    """Save the full ASGF session as a Class Material record.

    Creates a StudyGuide record with:
    - title: derived from the session question/topic
    - content: slides rendered as markdown + quiz results
    - guide_type: "study_guide"
    - Quiz results stored in learning_history
    - AI summary paragraph (1-2 sentences)

    Returns (study_guide_id, summary).
    """
    from app.models.student import Student

    # Look up learning_history for this session
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise ValueError(f"Session {session_id} not found in learning_history")

    # Get student info for summary
    student = db.query(Student).filter(Student.id == student_id).first()
    student_name = "The student"
    user_id = None
    if student and student.user:
        student_name = student.user.full_name or "The student"
        user_id = student.user_id
    elif student:
        user_id = student.user_id

    if user_id is None:
        raise ValueError(f"Cannot resolve user_id for student {student_id}")

    question = history_row.question_asked or "Study Session"
    subject = history_row.subject or "General"

    # Calculate quiz stats
    correct_count = sum(1 for q in quiz_results if q.get("correct"))
    total_count = len(quiz_results)
    total_xp = sum(q.get("xp_earned", 0) for q in quiz_results)
    avg_attempts = (
        sum(q.get("attempts", 1) for q in quiz_results) / total_count
        if total_count > 0
        else 0.0
    )
    score_pct = round(correct_count / total_count * 100) if total_count > 0 else 0

    # Generate AI summary
    summary = await _generate_summary(
        question=question,
        student_name=student_name,
        correct_count=correct_count,
        total_count=total_count,
        subject=subject,
    )

    # Build markdown content: slides + quiz + summary
    slide_md = _render_slides_as_markdown(slides)
    quiz_md = _render_quiz_markdown(quiz_results)
    content = f"# {question}\n\n{summary}\n\n---\n\n{slide_md}\n\n---\n\n{quiz_md}"

    # Create StudyGuide record
    title = f"Flash Study: {question[:200]}"
    study_guide = StudyGuide(
        user_id=user_id,
        title=title,
        content=content,
        guide_type="study_guide",
    )
    db.add(study_guide)
    db.flush()  # Get the ID before commit

    # Delegate quiz-result writing to the shared service (#3489)
    # This avoids duplicating score/weak-concept logic in two places.
    update_learning_history_on_complete(
        session_id=session_id, quiz_results=quiz_results, db=db,
    )

    # Set the material link (not handled by update_learning_history_on_complete)
    history_row.material_id = study_guide.id
    db.commit()  # Single commit for flush + quiz data + material_id (#3497)

    logger.info(
        "ASGF auto-save: session=%s, material_id=%d, score=%d%%, xp=%d",
        session_id,
        study_guide.id,
        score_pct,
        total_xp,
    )

    return study_guide.id, summary
