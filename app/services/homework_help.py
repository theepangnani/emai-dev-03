"""Homework Help Service — subject-specific AI tutoring with hint/explain/solve/check modes."""
from __future__ import annotations

import re
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.homework_help import HelpMode, HomeworkSavedSolution, HomeworkSession, SubjectArea
from app.models.student import Student

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mode-specific system prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPTS: dict[HelpMode, str] = {
    HelpMode.HINT: (
        "You are a patient and encouraging homework tutor. "
        "The student is asking for help — give 1–2 short, targeted hints to help them figure out the answer "
        "themselves. Do NOT give the full answer or solution. Use simple language appropriate for a student. "
        "Format hints as a numbered list."
    ),
    HelpMode.EXPLAIN: (
        "You are a knowledgeable and clear homework tutor. "
        "Explain the concept or theory behind the student's question step by step. "
        "Do not just give the answer — help the student understand *why* the approach works. "
        "Use numbered steps where appropriate."
    ),
    HelpMode.SOLVE: (
        "You are a clear and methodical homework tutor. "
        "Solve the problem showing every step clearly. "
        "Number each step and briefly explain what you are doing at each stage."
    ),
    HelpMode.CHECK: (
        "You are a helpful and encouraging homework tutor. "
        "The student has provided their own attempt at solving a problem. "
        "Check whether their work is correct. "
        "If it is correct, confirm it and briefly explain why. "
        "If it contains errors, point out the specific mistakes kindly and explain how to fix them. "
        "Do NOT simply re-solve the problem from scratch."
    ),
}

_SUBJECT_CONTEXT: dict[SubjectArea, str] = {
    SubjectArea.MATH: "This is a mathematics question.",
    SubjectArea.SCIENCE: "This is a science question (could be biology, chemistry, or physics).",
    SubjectArea.ENGLISH: "This is an English language arts question (reading, writing, grammar, or literature).",
    SubjectArea.HISTORY: "This is a history or social studies question.",
    SubjectArea.FRENCH: "This is a French language question. If the student writes in French, respond in French.",
    SubjectArea.GEOGRAPHY: "This is a geography question.",
    SubjectArea.OTHER: "This is a general academic question.",
}


def _parse_steps(text: str) -> list[str]:
    """Extract numbered steps from the AI response."""
    lines = text.splitlines()
    steps: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            steps.append(re.sub(r"^\d+[\.\)]\s+", "", stripped).strip())
    return steps


def _get_openai_client(student: Student | None = None) -> OpenAI:
    """Return OpenAI client, preferring the student's BYOK key when available."""
    api_key = settings.openai_api_key

    if student and student.user and student.user.ai_api_key_encrypted:
        try:
            from app.core.encryption import decrypt_api_key
            decrypted = decrypt_api_key(student.user.ai_api_key_encrypted)
            if decrypted:
                api_key = decrypted
        except Exception:
            pass  # Fall back to platform key

    return OpenAI(api_key=api_key)


class HomeworkHelpService:
    """Provides AI-powered homework assistance."""

    # ------------------------------------------------------------------
    # Core help
    # ------------------------------------------------------------------

    @staticmethod
    def get_help(
        student_id: int,
        subject: SubjectArea,
        question: str,
        mode: HelpMode,
        context: Optional[str],
        course_id: Optional[int],
        db: Session,
    ) -> HomeworkSession:
        student = db.query(Student).filter(Student.id == student_id).first()
        client = _get_openai_client(student)

        system_prompt = _SYSTEM_PROMPTS[mode]
        subject_context = _SUBJECT_CONTEXT.get(subject, "")

        user_message = f"{subject_context}\n\nQuestion: {question}"
        if mode == HelpMode.CHECK and context:
            user_message += f"\n\nStudent's attempt:\n{context}"
        elif context:
            user_message += f"\n\nAdditional context: {context}"

        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=1500,
                temperature=0.4,
            )
            response_text = completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI error in homework help: %s", exc)
            raise

        session = HomeworkSession(
            student_id=student_id,
            subject=subject,
            question=question,
            mode=mode,
            response=response_text,
            follow_up_count=0,
            course_id=course_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    # ------------------------------------------------------------------
    # Follow-up
    # ------------------------------------------------------------------

    @staticmethod
    def follow_up(
        session_id: int,
        student_id: int,
        follow_up: str,
        db: Session,
    ) -> HomeworkSession:
        session = (
            db.query(HomeworkSession)
            .filter(HomeworkSession.id == session_id, HomeworkSession.student_id == student_id)
            .first()
        )
        if not session:
            raise ValueError("Session not found or does not belong to this student")

        student = db.query(Student).filter(Student.id == student_id).first()
        client = _get_openai_client(student)

        system_prompt = _SYSTEM_PROMPTS.get(session.mode, _SYSTEM_PROMPTS[HelpMode.EXPLAIN])
        subject_context = _SUBJECT_CONTEXT.get(session.subject, "")

        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{subject_context}\n\nOriginal question: {session.question}"},
                    {"role": "assistant", "content": session.response},
                    {"role": "user", "content": follow_up},
                ],
                max_tokens=1200,
                temperature=0.4,
            )
            new_response = completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI error in homework follow-up: %s", exc)
            raise

        session.response = new_response
        session.follow_up_count += 1
        db.commit()
        db.refresh(session)
        return session

    # ------------------------------------------------------------------
    # Save solution
    # ------------------------------------------------------------------

    @staticmethod
    def save_solution(
        session_id: int,
        student_id: int,
        title: str,
        tags: Optional[list[str]],
        db: Session,
    ) -> HomeworkSavedSolution:
        session = (
            db.query(HomeworkSession)
            .filter(HomeworkSession.id == session_id, HomeworkSession.student_id == student_id)
            .first()
        )
        if not session:
            raise ValueError("Session not found or does not belong to this student")

        # Upsert — update if already saved
        existing = (
            db.query(HomeworkSavedSolution)
            .filter(HomeworkSavedSolution.session_id == session_id)
            .first()
        )
        if existing:
            existing.title = title
            existing.tags = tags or []
            db.commit()
            db.refresh(existing)
            return existing

        saved = HomeworkSavedSolution(
            student_id=student_id,
            session_id=session_id,
            title=title,
            tags=tags or [],
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_sessions(
        student_id: int,
        subject: Optional[SubjectArea],
        db: Session,
        limit: int = 50,
    ) -> list[HomeworkSession]:
        query = db.query(HomeworkSession).filter(HomeworkSession.student_id == student_id)
        if subject:
            query = query.filter(HomeworkSession.subject == subject)
        return query.order_by(HomeworkSession.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_saved_solutions(student_id: int, db: Session) -> list[HomeworkSavedSolution]:
        return (
            db.query(HomeworkSavedSolution)
            .filter(HomeworkSavedSolution.student_id == student_id)
            .order_by(HomeworkSavedSolution.created_at.desc())
            .all()
        )

    @staticmethod
    def delete_saved_solution(saved_id: int, student_id: int, db: Session) -> bool:
        saved = (
            db.query(HomeworkSavedSolution)
            .filter(HomeworkSavedSolution.id == saved_id, HomeworkSavedSolution.student_id == student_id)
            .first()
        )
        if not saved:
            return False
        db.delete(saved)
        db.commit()
        return True
