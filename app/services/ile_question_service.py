"""
ILE Question Generation Service — CB-ILE-001 (#3199).

Generates MCQ and fill-in-the-blank questions using AI, with
bank-first lookup for cost optimization.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_question_bank import ILEQuestionBank
from app.services.ai_service import generate_content, check_content_safe

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_MCQ_SYSTEM = (
    "You are an expert K-12 educational question writer. "
    "Generate multiple-choice questions that are clear, age-appropriate, "
    "and aligned with the Ontario curriculum where applicable. "
    "Return ONLY valid JSON with no markdown fences."
)

_MCQ_PROMPT = """\
Generate {count} multiple-choice questions for:
- Subject: {subject}
- Topic: {topic}
- Grade level: {grade_level}
- Difficulty: {difficulty}
- Bloom's taxonomy tier: {blooms_tier}

Requirements:
- Each question has exactly 4 options (A, B, C, D)
- Exactly one correct answer
- Distractors should be plausible but clearly wrong
- Use grade-appropriate language
- Avoid cultural or gender bias

Return a JSON array of objects with keys:
"question", "options" (object with A/B/C/D), "correct_answer" (A/B/C/D), "explanation" (1-2 sentences why correct), "difficulty", "blooms_tier"
"""

_FILL_BLANK_SYSTEM = (
    "You are an expert K-12 educational question writer. "
    "Generate fill-in-the-blank questions that are clear, age-appropriate, "
    "and aligned with the Ontario curriculum where applicable. "
    "Return ONLY valid JSON with no markdown fences."
)

_FILL_BLANK_PROMPT = """\
Generate {count} fill-in-the-blank questions for:
- Subject: {subject}
- Topic: {topic}
- Grade level: {grade_level}
- Difficulty: {difficulty}
- Bloom's taxonomy tier: {blooms_tier}

Requirements:
- Each question should have a clear blank to fill (use _____ in the question text)
- The correct answer should be a single word or short phrase (1-4 words)
- Answers should be unambiguous
- Use grade-appropriate language
- Avoid cultural or gender bias

Return a JSON array of objects with keys:
"question", "correct_answer" (the text that fills the blank), "explanation" (1-2 sentences why correct), "difficulty", "blooms_tier"

Do NOT include an "options" field — these are typed-answer questions.
"""

_HINT_SYSTEM = (
    "You are a patient K-12 tutor. Generate a scaffolding hint that "
    "guides the student toward the answer WITHOUT revealing it. "
    "Write at grade level. Keep it to 1-2 sentences."
)

_HINT_PROMPT = """\
The student got this wrong (attempt {attempt_number}):
Question: {question}
Student's wrong answer: {wrong_answer}
Correct answer: {correct_answer}

{previous_context}

Generate a hint that:
- Points toward the underlying concept
- Does NOT reveal the correct answer
- Is more specific than any previous hint
- Uses encouraging, non-judgmental language

Return ONLY the hint text, no JSON.
"""

_EXPLANATION_SYSTEM = (
    "You are an expert K-12 educator. Explain why an answer is correct "
    "in 2-3 sentences at grade level. Be clear and educational."
)

_EXPLANATION_PROMPT = """\
Question: {question}
Correct answer: {correct_answer}
Grade level: {grade_level}

Explain why this is the correct answer in 2-3 sentences.
Use language appropriate for grade {grade_level}.
Return ONLY the explanation text, no JSON.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_questions(
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
    blooms_tier: str = "recall",
    count: int = 5,
    question_format: str = "mcq",
    context_text: str | None = None,
) -> list[dict]:
    """Generate quiz questions via AI.

    Returns a list of question dicts with keys:
    question, options, correct_answer, explanation, difficulty, blooms_tier

    If context_text is provided, questions are grounded in that study material.
    """
    if question_format == "fill_blank":
        prompt = _FILL_BLANK_PROMPT.format(
            count=count,
            subject=subject,
            topic=topic,
            grade_level=grade_level or "middle school",
            difficulty=difficulty,
            blooms_tier=blooms_tier,
        )
        system_prompt = _FILL_BLANK_SYSTEM
    else:
        prompt = _MCQ_PROMPT.format(
            count=count,
            subject=subject,
            topic=topic,
            grade_level=grade_level or "middle school",
            difficulty=difficulty,
            blooms_tier=blooms_tier,
        )
        system_prompt = _MCQ_SYSTEM

    # Ground questions in study material when context is provided
    if context_text:
        truncated = context_text[:2000]
        prompt = (
            f"Generate questions based on the following study material:\n\n"
            f"---\n{truncated}\n---\n\n{prompt}"
        )

    content, _ = await generate_content(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=2000,
        temperature=0.8,
    )

    questions = _parse_questions_json(content)
    if not questions:
        logger.error("Failed to parse AI questions for %s/%s", subject, topic)
        raise ValueError("AI returned invalid question format")

    # Validate each question
    validated = []
    for q in questions[:count]:
        if _validate_question(q):
            validated.append(q)

    if len(validated) < count:
        logger.warning(
            "Only %d/%d questions validated for %s/%s",
            len(validated), count, subject, topic,
        )

    if not validated:
        raise ValueError("No valid questions generated")

    # Tag format on each question
    for q in validated:
        q["format"] = question_format

    # Content safety check on AI-generated questions
    safe_questions = []
    for q in validated:
        is_safe, reason = check_content_safe(q["question"])
        if is_safe:
            safe_questions.append(q)
        else:
            logger.warning("Filtered unsafe question: %s", reason)

    if len(safe_questions) < len(validated):
        logger.warning(
            "Content safety filtered %d/%d questions for %s/%s",
            len(validated) - len(safe_questions), len(validated), subject, topic,
        )

    if not safe_questions:
        raise ValueError("No safe questions generated")

    return safe_questions


async def generate_hint(
    question: str,
    wrong_answer: str,
    correct_answer: str,
    attempt_number: int,
    previous_hints: list[str] | None = None,
    grade_level: int | None = None,
) -> str:
    """Generate a scaffolding hint for a wrong answer."""
    previous_context = ""
    if previous_hints:
        prev = "\n".join(f"- Hint {i+1}: {h}" for i, h in enumerate(previous_hints))
        previous_context = f"Previous hints given:\n{prev}\nMake this hint MORE specific."

    prompt = _HINT_PROMPT.format(
        attempt_number=attempt_number,
        question=question,
        wrong_answer=wrong_answer,
        correct_answer=correct_answer,
        previous_context=previous_context,
    )

    content, _ = await generate_content(
        prompt=prompt,
        system_prompt=_HINT_SYSTEM,
        max_tokens=200,
        temperature=0.7,
    )
    return content.strip()


async def generate_explanation(
    question: str,
    correct_answer: str,
    grade_level: int | None = None,
) -> str:
    """Generate a 'Why Correct' explanation."""
    prompt = _EXPLANATION_PROMPT.format(
        question=question,
        correct_answer=correct_answer,
        grade_level=grade_level or 8,
    )

    content, _ = await generate_content(
        prompt=prompt,
        system_prompt=_EXPLANATION_SYSTEM,
        max_tokens=300,
        temperature=0.7,
    )
    return content.strip()


def get_from_bank(
    db: Session,
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
    count: int = 5,
    exclude_ids: list[int] | None = None,
    question_format: str = "mcq",
) -> list[dict]:
    """Retrieve pre-generated questions from the bank.

    Returns list of question dicts (may be fewer than count).
    Filters by question_format at the DB level so the composite index
    (subject, topic, grade_level, difficulty, question_format) is used.
    """
    now = datetime.now(timezone.utc)
    query = (
        db.query(ILEQuestionBank)
        .filter(
            ILEQuestionBank.subject == subject,
            ILEQuestionBank.topic == topic,
            ILEQuestionBank.grade_level == grade_level,
            ILEQuestionBank.difficulty == difficulty,
            ILEQuestionBank.question_format == question_format,
            ILEQuestionBank.flagged == False,  # noqa: E712
            (ILEQuestionBank.expires_at > now) | (ILEQuestionBank.expires_at.is_(None)),
        )
    )
    if exclude_ids:
        query = query.filter(ILEQuestionBank.id.notin_(exclude_ids))

    bank_items = query.order_by(ILEQuestionBank.times_served).limit(count).all()

    questions = []
    for item in bank_items:
        try:
            q = json.loads(item.question_json)
            q["_bank_id"] = item.id
            if item.explanation_text:
                q["explanation"] = item.explanation_text
            if item.hint_tree_json:
                q["_hint_tree"] = json.loads(item.hint_tree_json)
            questions.append(q)
            # Increment serve count
            item.times_served += 1
        except Exception:
            logger.warning("Corrupt question bank entry %d", item.id)
    if questions:
        db.commit()
    return questions


def check_format_escalation(db: Session, student_id: int, subject: str, topic: str) -> str:
    """Check if student should escalate from MCQ to fill_blank.

    Rule: After 2 correct MCQ sessions (score >= 80%) on same topic -> fill_blank.
    Uses ile_topic_mastery.mcq_correct_streak field.
    """
    from app.models.ile_topic_mastery import ILETopicMastery

    mastery = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.subject == subject,
            ILETopicMastery.topic == topic,
        )
        .first()
    )
    if mastery and mastery.mcq_correct_streak >= 2:
        # Check if student is struggling with fill_blank — de-escalate if needed
        from app.models.ile_session import ILESession

        recent_fill_blank = (
            db.query(ILESession)
            .filter(
                ILESession.student_id == student_id,
                ILESession.subject == subject,
                ILESession.topic == topic,
                ILESession.status == "completed",
            )
            .order_by(ILESession.completed_at.desc())
            .limit(2)
            .all()
        )

        # If last 2 sessions scored < 50%, de-escalate to MCQ
        poor_sessions = [
            s for s in recent_fill_blank
            if s.score is not None
            and s.total_correct is not None
            and s.question_count > 0
            and (s.total_correct / s.question_count * 100) < 50
        ]
        if len(poor_sessions) >= 2:
            logger.info(
                "Format de-escalation: fill_blank->mcq for student=%d topic=%s/%s",
                student_id, subject, topic,
            )
            return "mcq"

        logger.info(
            "Format escalation: mcq->fill_blank for student=%d topic=%s/%s (streak=%d)",
            student_id, subject, topic, mastery.mcq_correct_streak,
        )
        return "fill_blank"
    return "mcq"


async def get_from_bank_or_generate(
    db: Session,
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
    blooms_tier: str = "recall",
    count: int = 5,
    question_format: str = "mcq",
    context_text: str | None = None,
) -> list[dict]:
    """Try bank first, fall back to on-demand generation.

    When context_text is provided, skip the bank and always generate fresh
    questions grounded in the study material.
    """
    # Context-grounded questions bypass the bank — they are specific to the material
    if context_text:
        logger.info(
            "Context-grounded generation for %s/%s (context_len=%d)",
            subject, topic, len(context_text),
        )
        return await generate_questions(
            subject, topic, grade_level, difficulty, blooms_tier, count,
            question_format=question_format,
            context_text=context_text,
        )

    bank_questions = get_from_bank(
        db, subject, topic, grade_level, difficulty, count,
        question_format=question_format,
    )

    if len(bank_questions) >= count:
        logger.info("Served %d questions from bank for %s/%s", count, subject, topic)
        return bank_questions[:count]

    # Generate remaining
    remaining = count - len(bank_questions)
    logger.info(
        "Bank had %d/%d questions for %s/%s (format=%s), generating %d",
        len(bank_questions), count, subject, topic, question_format, remaining,
    )
    generated = await generate_questions(
        subject, topic, grade_level, difficulty, blooms_tier, remaining,
        question_format=question_format,
    )

    # Save newly generated questions to bank for future reuse
    if generated and db is not None:
        try:
            from app.services.ile_cost_optimizer import save_questions_to_bank
            save_questions_to_bank(
                db, generated, subject, topic, grade_level, difficulty,
            )
        except Exception:
            logger.warning("Failed to save generated questions to bank", exc_info=True)

    return bank_questions + generated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_questions_json(content: str) -> list[dict] | None:
    """Parse AI response into list of question dicts, stripping markdown fences."""
    text = content.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
    except json.JSONDecodeError:
        # Try to find JSON array in the content
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _validate_question(q: dict) -> bool:
    """Validate a question dict has required fields."""
    required = {"question", "correct_answer"}
    if not all(k in q for k in required):
        return False
    if "options" in q:
        # MCQ validation
        opts = q["options"]
        if not isinstance(opts, dict) or not all(k in opts for k in "ABCD"):
            return False
        if q["correct_answer"] not in "ABCD":
            return False
    else:
        # Fill-in-the-blank validation
        answer = q["correct_answer"]
        if not isinstance(answer, str) or not answer.strip():
            return False
        # Warn if question text has no blank indicator (still valid, just suboptimal)
        if "_____" not in q["question"] and "____" not in q["question"] and "___" not in q["question"]:
            logger.warning("Fill-blank question missing blank indicator: %.80s", q["question"])
    return True
