"""
LearningJournalService — business logic for the course learning journal feature.
"""
from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.learning_journal import JournalEntry, JournalMood, JournalReflectionPrompt
from app.schemas.learning_journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalStats,
    ReflectionPromptResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default reflection prompts (15 across all categories)
# ---------------------------------------------------------------------------
DEFAULT_PROMPTS: list[dict] = [
    # weekly_review
    {"prompt_text": "What was the most important thing you learned this week and why does it matter?", "category": "weekly_review"},
    {"prompt_text": "Describe a moment this week where something finally 'clicked' for you.", "category": "weekly_review"},
    {"prompt_text": "What topic took the most effort this week? How did you tackle it?", "category": "weekly_review"},
    {"prompt_text": "If you could revisit one lesson from this week, which would it be and what would you do differently?", "category": "weekly_review"},
    # concept_check
    {"prompt_text": "Choose a concept you studied today. How would you explain it to a 10-year-old?", "category": "concept_check"},
    {"prompt_text": "What connection did you notice between today's material and something you already knew?", "category": "concept_check"},
    {"prompt_text": "What question about today's topic are you still sitting with? What might help you answer it?", "category": "concept_check"},
    {"prompt_text": "Write out the steps you take to solve a type of problem you encountered in class today.", "category": "concept_check"},
    # goal_check
    {"prompt_text": "What is one specific academic goal you have for the next two weeks? How will you know you achieved it?", "category": "goal_check"},
    {"prompt_text": "Reflect on a goal you set last week. Did you reach it? What helped or hindered you?", "category": "goal_check"},
    {"prompt_text": "What study habit would you like to build and what is your first small step?", "category": "goal_check"},
    # emotion_check
    {"prompt_text": "On a scale of 1-10, how confident are you feeling about the current unit? What would move that number up?", "category": "emotion_check"},
    {"prompt_text": "Is there anything about school right now that feels overwhelming? What is one thing you can control about it?", "category": "emotion_check"},
    {"prompt_text": "Write about a time this week you felt proud of yourself as a learner.", "category": "emotion_check"},
    {"prompt_text": "What would make studying feel more enjoyable or meaningful for you?", "category": "emotion_check"},
]


def _count_words(text: str) -> int:
    return len(text.split()) if text else 0


class LearningJournalService:

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def create_entry(student_id: int, data: JournalEntryCreate, db: Session) -> JournalEntry:
        entry = JournalEntry(
            student_id=student_id,
            course_id=data.course_id,
            title=data.title,
            content=data.content,
            mood=data.mood,
            tags=data.tags or [],
            ai_prompt_used=data.ai_prompt_used,
            is_teacher_visible=data.is_teacher_visible,
            word_count=_count_words(data.content),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def update_entry(
        entry_id: int, student_id: int, data: JournalEntryUpdate, db: Session
    ) -> JournalEntry:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.student_id == student_id)
            .first()
        )
        if not entry:
            return None  # type: ignore[return-value]

        if data.title is not None:
            entry.title = data.title
        if data.content is not None:
            entry.content = data.content
            entry.word_count = _count_words(data.content)
        if data.mood is not None:
            entry.mood = data.mood
        if data.tags is not None:
            entry.tags = data.tags
        if data.course_id is not None:
            entry.course_id = data.course_id
        if data.is_teacher_visible is not None:
            entry.is_teacher_visible = data.is_teacher_visible

        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def delete_entry(entry_id: int, student_id: int, db: Session) -> bool:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.student_id == student_id)
            .first()
        )
        if not entry:
            return False
        db.delete(entry)
        db.commit()
        return True

    @staticmethod
    def get_entries(
        student_id: int,
        db: Session,
        course_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[JournalEntry], int]:
        """Return (entries, total_count) for the given student."""
        q = db.query(JournalEntry).filter(JournalEntry.student_id == student_id)
        if course_id is not None:
            q = q.filter(JournalEntry.course_id == course_id)
        total = q.count()
        entries = (
            q.order_by(JournalEntry.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return entries, total

    @staticmethod
    def get_entry(entry_id: int, requester_id: int, db: Session) -> Optional[JournalEntry]:
        """
        Returns the entry if:
        - requester is the student owner, OR
        - the entry is teacher-visible (teacher scenario — we trust route layer for role check)
        """
        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            return None
        if entry.student_id == requester_id:
            return entry
        if entry.is_teacher_visible:
            return entry
        return None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @staticmethod
    def get_stats(student_id: int, db: Session) -> JournalStats:
        entries = (
            db.query(JournalEntry)
            .filter(JournalEntry.student_id == student_id)
            .all()
        )

        total = len(entries)
        avg_words = round(sum(e.word_count for e in entries) / total, 1) if total else 0.0

        # Mood distribution
        mood_dist: dict[str, int] = {m.value: 0 for m in JournalMood}
        for e in entries:
            if e.mood:
                mood_dist[e.mood.value] = mood_dist.get(e.mood.value, 0) + 1

        # Streak: consecutive calendar days with at least one entry (up to today)
        today = date.today()
        entry_dates = {e.created_at.date() for e in entries if e.created_at}
        streak = 0
        check = today
        while check in entry_dates:
            streak += 1
            check -= timedelta(days=1)

        # Entries this week (Mon–Sun)
        week_start = today - timedelta(days=today.weekday())
        entries_this_week = sum(
            1 for e in entries if e.created_at and e.created_at.date() >= week_start
        )

        return JournalStats(
            total_entries=total,
            avg_words=avg_words,
            mood_distribution=mood_dist,
            streak_days=streak,
            entries_this_week=entries_this_week,
        )

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    @staticmethod
    def get_random_prompt(db: Session, category: Optional[str] = None) -> Optional[JournalReflectionPrompt]:
        q = db.query(JournalReflectionPrompt).filter(JournalReflectionPrompt.is_active == True)  # noqa: E712
        if category:
            q = q.filter(JournalReflectionPrompt.category == category)
        prompts = q.all()
        return random.choice(prompts) if prompts else None

    @staticmethod
    def get_all_prompts(db: Session) -> list[JournalReflectionPrompt]:
        return (
            db.query(JournalReflectionPrompt)
            .filter(JournalReflectionPrompt.is_active == True)  # noqa: E712
            .order_by(JournalReflectionPrompt.category, JournalReflectionPrompt.id)
            .all()
        )

    @staticmethod
    def get_ai_reflection_prompt(
        student_id: int, db: Session, context: str = "general"
    ) -> ReflectionPromptResponse:
        """
        Generate a personalised reflection question via GPT-4o-mini based on the
        student's recent activity.  Falls back to a random seed prompt on error.
        """
        try:
            from app.core.config import settings
            from openai import OpenAI

            # Gather recent entries for context
            recent_entries = (
                db.query(JournalEntry)
                .filter(JournalEntry.student_id == student_id)
                .order_by(JournalEntry.created_at.desc())
                .limit(3)
                .all()
            )

            context_text = ""
            if recent_entries:
                snippets = [
                    f"- [{e.created_at.strftime('%b %d')}] {(e.title or 'entry')}: {e.content[:120]}..."
                    for e in recent_entries
                ]
                context_text = "Recent journal entries:\n" + "\n".join(snippets)
            else:
                context_text = "This student is new to journaling."

            system_msg = (
                "You are a supportive learning coach for a secondary or post-secondary student. "
                "Your job is to write ONE concise (1-2 sentence) reflective journal prompt that "
                "encourages the student to think deeply about their learning. "
                "Be warm, encouraging, and academically focused. "
                "Do NOT answer the question — just pose it."
            )
            user_msg = (
                f"Context: {context}\n\n"
                f"{context_text}\n\n"
                "Generate one personalised reflection question for this student."
            )

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=120,
                temperature=0.8,
            )
            prompt_text = response.choices[0].message.content.strip()

            return ReflectionPromptResponse(
                id=None,
                prompt_text=prompt_text,
                category="ai_generated",
                is_ai_generated=True,
            )

        except Exception as exc:
            logger.warning("AI prompt generation failed (%s), falling back to seed prompt", exc)
            fallback = LearningJournalService.get_random_prompt(db)
            if fallback:
                return ReflectionPromptResponse(
                    id=fallback.id,
                    prompt_text=fallback.prompt_text,
                    category=fallback.category,
                    is_ai_generated=False,
                )
            # Absolute fallback
            return ReflectionPromptResponse(
                id=None,
                prompt_text="What is one thing you learned today and how does it connect to what you already know?",
                category="concept_check",
                is_ai_generated=False,
            )

    # ------------------------------------------------------------------
    # Teacher-visible entries
    # ------------------------------------------------------------------

    @staticmethod
    def get_teacher_visible_entries(
        teacher_id: int, course_id: int, db: Session
    ) -> list[JournalEntry]:
        """
        Returns all journal entries for a course that students have shared with teachers.
        Requires the teacher to teach that course (validated at route level).
        """
        return (
            db.query(JournalEntry)
            .filter(
                JournalEntry.course_id == course_id,
                JournalEntry.is_teacher_visible == True,  # noqa: E712
            )
            .order_by(JournalEntry.created_at.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    @staticmethod
    def seed_prompts(db: Session) -> None:
        """Idempotently insert the 15 default reflection prompts."""
        existing_count = db.query(JournalReflectionPrompt).count()
        if existing_count >= len(DEFAULT_PROMPTS):
            return  # Already seeded

        existing_texts = {p.prompt_text for p in db.query(JournalReflectionPrompt).all()}
        for prompt_data in DEFAULT_PROMPTS:
            if prompt_data["prompt_text"] not in existing_texts:
                db.add(JournalReflectionPrompt(**prompt_data))
        db.commit()
        logger.info("Seeded %d learning journal reflection prompts", len(DEFAULT_PROMPTS))
