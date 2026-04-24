"""Tests for LearningCycleSession / Chunk / Question / Answer models (#4067)."""
from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect


def _make_user(db, email):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=email,
        full_name=email.split("@")[0],
        role=UserRole("student"),
        hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.flush()
    return user


def _make_session(db, user_id, topic="Fractions", subject="Math"):
    from app.models.learning_cycle import LearningCycleSession

    session = LearningCycleSession(
        user_id=user_id,
        topic=topic,
        subject=subject,
        grade_level=5,
    )
    db.add(session)
    db.flush()
    return session


class TestLearningCycleSchema:
    def test_all_four_tables_exist(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        names = set(inspector.get_table_names())
        for t in (
            "learning_cycle_sessions",
            "learning_cycle_chunks",
            "learning_cycle_questions",
            "learning_cycle_answers",
        ):
            assert t in names, f"table {t} should be auto-created by create_all()"

    def test_session_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("learning_cycle_sessions")}
        assert cols >= {
            "id",
            "user_id",
            "topic",
            "subject",
            "grade_level",
            "status",
            "current_chunk_idx",
            "created_at",
            "completed_at",
        }

    def test_chunk_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("learning_cycle_chunks")}
        assert cols >= {
            "id",
            "session_id",
            "order",
            "teach_content_md",
            "mastery_status",
        }

    def test_question_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("learning_cycle_questions")}
        assert cols >= {
            "id",
            "chunk_id",
            "order",
            "format",
            "prompt",
            "options",
            "correct_answer",
            "explanation",
        }

    def test_answer_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("learning_cycle_answers")}
        assert cols >= {
            "id",
            "question_id",
            "attempt_number",
            "answer_given",
            "is_correct",
            "xp_awarded",
            "created_at",
        }


class TestLearningCycleCrud:
    def test_create_session_defaults(self, db_session):
        from app.models.learning_cycle import LearningCycleSession

        user = _make_user(db_session, "lc_user1@test.com")
        s = LearningCycleSession(
            user_id=user.id, topic="Photosynthesis", subject="Science"
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        assert s.id is not None
        assert len(s.id) == 36  # UUID string
        assert s.status == "active"
        assert s.current_chunk_idx == 0
        assert s.created_at is not None
        assert s.completed_at is None

    def test_add_chunks_and_questions_and_answers(self, db_session):
        from app.models.learning_cycle import (
            LearningCycleAnswer,
            LearningCycleChunk,
            LearningCycleQuestion,
        )

        user = _make_user(db_session, "lc_user2@test.com")
        session = _make_session(db_session, user.id)

        chunk = LearningCycleChunk(
            session_id=session.id,
            order=0,
            teach_content_md="# What is a fraction?\n\nA fraction is...",
        )
        db_session.add(chunk)
        db_session.flush()

        q = LearningCycleQuestion(
            chunk_id=chunk.id,
            order=0,
            format="mcq",
            prompt="Which of these is a fraction?",
            options={"A": "1/2", "B": "5", "C": "cat", "D": "-"},
            correct_answer="A",
            explanation="1/2 is a fraction because it has a numerator and denominator.",
        )
        db_session.add(q)
        db_session.flush()

        a = LearningCycleAnswer(
            question_id=q.id,
            attempt_number=1,
            answer_given="A",
            is_correct=True,
            xp_awarded=10,
        )
        db_session.add(a)
        db_session.commit()

        db_session.refresh(session)
        assert len(session.chunks) == 1
        assert len(session.chunks[0].questions) == 1
        assert len(session.chunks[0].questions[0].answers) == 1
        assert session.chunks[0].questions[0].answers[0].is_correct is True
        assert session.chunks[0].questions[0].answers[0].xp_awarded == 10
        # JSON round-trip
        assert session.chunks[0].questions[0].options == {
            "A": "1/2",
            "B": "5",
            "C": "cat",
            "D": "-",
        }

    def test_answer_defaults(self, db_session):
        from app.models.learning_cycle import (
            LearningCycleAnswer,
            LearningCycleChunk,
            LearningCycleQuestion,
        )

        user = _make_user(db_session, "lc_user3@test.com")
        session = _make_session(db_session, user.id)
        chunk = LearningCycleChunk(
            session_id=session.id, order=0, teach_content_md="x"
        )
        db_session.add(chunk)
        db_session.flush()
        q = LearningCycleQuestion(
            chunk_id=chunk.id,
            order=0,
            format="true_false",
            prompt="The sky is blue.",
            correct_answer="true",
            explanation="On a clear day.",
        )
        db_session.add(q)
        db_session.flush()

        a = LearningCycleAnswer(question_id=q.id, answer_given="true")
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)

        assert a.attempt_number == 1
        assert a.is_correct is False
        assert a.xp_awarded == 0
        assert a.created_at is not None


class TestLearningCycleCascades:
    def test_delete_session_cascades_chunks_questions_answers(self, db_session):
        from app.models.learning_cycle import (
            LearningCycleAnswer,
            LearningCycleChunk,
            LearningCycleQuestion,
            LearningCycleSession,
        )

        user = _make_user(db_session, "lc_casc@test.com")
        session = _make_session(db_session, user.id)
        chunk = LearningCycleChunk(
            session_id=session.id, order=0, teach_content_md="x"
        )
        db_session.add(chunk)
        db_session.flush()
        q = LearningCycleQuestion(
            chunk_id=chunk.id,
            order=0,
            format="fill_blank",
            prompt="2+2=___",
            correct_answer="4",
            explanation="Basic addition.",
        )
        db_session.add(q)
        db_session.flush()
        a = LearningCycleAnswer(
            question_id=q.id, answer_given="4", is_correct=True
        )
        db_session.add(a)
        db_session.commit()

        session_id = session.id
        chunk_id = chunk.id
        q_id = q.id
        a_id = a.id

        db_session.delete(session)
        db_session.commit()

        assert (
            db_session.query(LearningCycleSession)
            .filter(LearningCycleSession.id == session_id)
            .first()
            is None
        )
        assert (
            db_session.query(LearningCycleChunk)
            .filter(LearningCycleChunk.id == chunk_id)
            .first()
            is None
        )
        assert (
            db_session.query(LearningCycleQuestion)
            .filter(LearningCycleQuestion.id == q_id)
            .first()
            is None
        )
        assert (
            db_session.query(LearningCycleAnswer)
            .filter(LearningCycleAnswer.id == a_id)
            .first()
            is None
        )

    def test_delete_user_cascades_session(self, db_session):
        from app.models.learning_cycle import LearningCycleSession

        user = _make_user(db_session, "lc_user_casc@test.com")
        session = _make_session(db_session, user.id)
        session_id = session.id

        db_session.delete(user)
        db_session.commit()

        assert (
            db_session.query(LearningCycleSession)
            .filter(LearningCycleSession.id == session_id)
            .first()
            is None
        )


class TestLearningCycleEnumConstraints:
    def test_session_status_rejects_invalid(self, db_session):
        from app.models.learning_cycle import LearningCycleSession

        user = _make_user(db_session, "lc_badstatus@test.com")
        s = LearningCycleSession(
            user_id=user.id,
            topic="T",
            subject="S",
            status="nonsense",
        )
        db_session.add(s)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_chunk_mastery_rejects_invalid(self, db_session):
        from app.models.learning_cycle import LearningCycleChunk

        user = _make_user(db_session, "lc_badmastery@test.com")
        session = _make_session(db_session, user.id)
        chunk = LearningCycleChunk(
            session_id=session.id,
            order=0,
            teach_content_md="x",
            mastery_status="bogus",
        )
        db_session.add(chunk)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_question_format_rejects_invalid(self, db_session):
        from app.models.learning_cycle import (
            LearningCycleChunk,
            LearningCycleQuestion,
        )

        user = _make_user(db_session, "lc_badformat@test.com")
        session = _make_session(db_session, user.id)
        chunk = LearningCycleChunk(
            session_id=session.id, order=0, teach_content_md="x"
        )
        db_session.add(chunk)
        db_session.flush()
        q = LearningCycleQuestion(
            chunk_id=chunk.id,
            order=0,
            format="essay",  # invalid
            prompt="p",
            correct_answer="a",
            explanation="e",
        )
        db_session.add(q)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_question_format_accepts_all_valid(self, db_session):
        from app.models.learning_cycle import (
            LearningCycleChunk,
            LearningCycleQuestion,
        )

        user = _make_user(db_session, "lc_goodformat@test.com")
        session = _make_session(db_session, user.id)
        chunk = LearningCycleChunk(
            session_id=session.id, order=0, teach_content_md="x"
        )
        db_session.add(chunk)
        db_session.flush()

        for i, fmt in enumerate(("mcq", "true_false", "fill_blank")):
            q = LearningCycleQuestion(
                chunk_id=chunk.id,
                order=i,
                format=fmt,
                prompt="p",
                correct_answer="a",
                explanation="e",
            )
            db_session.add(q)
        db_session.commit()
        assert len(chunk.questions) == 3
