"""TutorMatchingEngine — AI-powered tutor matching for Phase 4.

Computes a 100-point weighted match score between a student and each TutorProfile:
  - Subject match      35 pts  (weak subjects covered by tutor)
  - Grade level match  20 pts  (tutor teaches the student's grade)
  - Rating             20 pts  (avg_rating / 5.0 * 20)
  - Learning style     15 pts  (bio keyword alignment with student's style)
  - Price              10 pts  (affordability within stated preference)

Falls back gracefully when personalization data is absent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.personalization import PersonalizationProfile, SubjectMastery
from app.models.student import Student
from app.models.tutor_profile import TutorProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Learning-style keyword mapping
# ---------------------------------------------------------------------------

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "visual": [
        "visual", "diagram", "chart", "graph", "visual aids",
        "colour", "color", "whiteboard", "draw", "illustration",
    ],
    "auditory": [
        "explain", "discuss", "verbal", "talk", "conversation",
        "lecture", "listen", "speak", "audio",
    ],
    "reading": [
        "notes", "textbook", "reading", "written", "document",
        "handout", "text", "book", "outline", "summary",
    ],
    "kinesthetic": [
        "practice", "example", "hands-on", "exercise", "problem",
        "apply", "activity", "interactive", "step-by-step", "worksheet",
    ],
}

# Default style match when no profile exists (neutral)
_DEFAULT_STYLE_SCORE = 0.7


# ---------------------------------------------------------------------------
# Data class for a single match result
# ---------------------------------------------------------------------------

@dataclass
class TutorMatchScore:
    tutor_id: int
    tutor: TutorProfile
    score: float               # 0-100 overall weighted score
    subject_match: float       # raw points (0-35)
    grade_match: float         # raw points (0-20)
    rating_score: float        # raw points (0-20)
    style_match: float         # raw points (0-15)
    price_score: float         # raw points (0-10)
    explanation: str = ""
    covered_weak_subjects: list[str] = field(default_factory=list)
    total_weak_subjects: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TutorMatchingEngine:
    """Stateless matching engine — all state is in the database."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_match_score(
        self,
        tutor: TutorProfile,
        student_id: int,
        db: Session,
        preferences: dict | None = None,
    ) -> TutorMatchScore:
        """Score a single tutor against a student and optional preferences dict."""
        pref = preferences or {}

        tutor_subjects = self._parse_json_list(tutor.subjects)
        tutor_grades = self._parse_json_list(tutor.grade_levels)

        # 1. Subject match (35 pts)
        weak_subjects = self._get_weak_subjects(student_id, db)
        covered, subject_pts = self._score_subjects(tutor_subjects, weak_subjects)

        # 2. Grade match (20 pts)
        student_grade = self._get_student_grade(student_id, db)
        grade_pts = self._score_grade(tutor_grades, student_grade)

        # 3. Rating (20 pts)
        rating_pts = self._score_rating(tutor.avg_rating)

        # 4. Learning style (15 pts)
        learning_style = self._get_learning_style(student_id, db)
        style_pts = self._score_style(tutor.bio or "", tutor.headline or "", learning_style)

        # 5. Price (10 pts)
        max_rate = pref.get("max_hourly_rate_cad") or None
        price_pts = self._score_price(tutor.hourly_rate_cad, max_rate)

        total = subject_pts + grade_pts + rating_pts + style_pts + price_pts

        explanation = self._build_explanation(
            tutor=tutor,
            covered=covered,
            weak_subjects=weak_subjects,
            grade_pts=grade_pts,
            rating_pts=rating_pts,
            style_pts=style_pts,
            price_pts=price_pts,
            learning_style=learning_style,
        )

        return TutorMatchScore(
            tutor_id=tutor.id,
            tutor=tutor,
            score=round(total, 1),
            subject_match=round(subject_pts, 1),
            grade_match=round(grade_pts, 1),
            rating_score=round(rating_pts, 1),
            style_match=round(style_pts, 1),
            price_score=round(price_pts, 1),
            explanation=explanation,
            covered_weak_subjects=covered,
            total_weak_subjects=len(weak_subjects),
        )

    def rank_tutors(
        self,
        tutors: list[TutorProfile],
        student_id: int,
        db: Session,
        preferences: dict | None = None,
    ) -> list[TutorMatchScore]:
        """Score and sort all tutors descending by match score."""
        scores: list[TutorMatchScore] = []
        for tutor in tutors:
            try:
                match = self.compute_match_score(tutor, student_id, db, preferences)
                scores.append(match)
            except Exception as exc:
                logger.warning("Failed to score tutor %d: %s", tutor.id, exc)
        scores.sort(key=lambda m: m.score, reverse=True)
        return scores

    def get_top_matches(
        self,
        student_id: int,
        db: Session,
        limit: int = 10,
        preferences: dict | None = None,
    ) -> list[TutorMatchScore]:
        """Fetch all active tutors, score them, return the top N."""
        pref = preferences or {}
        q = db.query(TutorProfile).filter(
            TutorProfile.is_active == True,  # noqa: E712
            TutorProfile.is_accepting_students == True,  # noqa: E712
        )
        # Apply hard preference filters before scoring
        if pref.get("prefer_verified_only"):
            q = q.filter(TutorProfile.is_verified == True)  # noqa: E712
        if pref.get("min_rating") is not None:
            q = q.filter(
                (TutorProfile.avg_rating >= pref["min_rating"])
                | (TutorProfile.avg_rating == None)  # noqa: E711
            )
        if pref.get("max_hourly_rate_cad") is not None:
            q = q.filter(TutorProfile.hourly_rate_cad <= pref["max_hourly_rate_cad"])

        tutors = q.all()
        ranked = self.rank_tutors(tutors, student_id, db, preferences)
        return ranked[:limit]

    async def generate_ai_explanation(
        self,
        match: TutorMatchScore,
        student_profile: PersonalizationProfile | None,
    ) -> str:
        """Generate a personalised match explanation using the AI service."""
        from app.services.ai_service import generate_content

        tutor = match.tutor
        tutor_name = tutor.user.full_name if tutor.user else "This tutor"
        subjects_str = ", ".join(match.covered_weak_subjects) if match.covered_weak_subjects else "various subjects"
        style = (student_profile.learning_style if student_profile else None) or "general"
        rating = f"{tutor.avg_rating:.1f}-star" if tutor.avg_rating else "new"

        prompt = f"""You are a helpful education advisor. Write a personalized 2-3 sentence explanation
of why this tutor is a great match for this student.

Tutor: {tutor_name}
Tutor subjects: {', '.join(self._parse_json_list(tutor.subjects))}
Tutor bio excerpt: {(tutor.bio or '')[:200]}
Rating: {tutor.avg_rating or 'No rating yet'}
Hourly rate: ${tutor.hourly_rate_cad}/hr

Student learning style: {style}
Student weak subjects covered by this tutor: {subjects_str}
Overall match score: {match.score:.0f}/100

Write in second person ("Based on your..."), be specific, and mention subjects and rating.
Do not use markdown. Keep it to 2-3 sentences maximum."""

        try:
            result = await generate_content(
                prompt,
                system_prompt=(
                    "You are an educational advisor writing concise, personalized tutor match "
                    "explanations. Be friendly, specific, and informative. No markdown."
                ),
                max_tokens=200,
                temperature=0.5,
            )
            return result.strip()
        except Exception as exc:
            logger.warning("AI explanation generation failed: %s", exc)
            return match.explanation

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _score_subjects(
        self,
        tutor_subjects: list[str],
        weak_subjects: list[str],
    ) -> tuple[list[str], float]:
        """Return (covered_list, points_0_to_35)."""
        if not weak_subjects:
            # No mastery data — give half credit (tutor is potentially useful)
            return [], 17.5

        tutor_lower = [s.lower() for s in tutor_subjects]
        covered = []
        for ws in weak_subjects:
            ws_lower = ws.lower()
            # Partial substring match to handle "Mathematics" vs "Math"
            for ts in tutor_lower:
                if ws_lower in ts or ts in ws_lower:
                    covered.append(ws)
                    break

        ratio = len(covered) / max(len(weak_subjects), 1)
        return covered, ratio * 35.0

    def _score_grade(self, tutor_grades: list[str], student_grade: int | None) -> float:
        """Return points 0-20 for grade level match."""
        if student_grade is None or not tutor_grades:
            return 10.0  # neutral — no data

        student_str = str(student_grade)
        if student_str in tutor_grades:
            return 20.0

        # Partial credit for adjacent grades
        for tg in tutor_grades:
            try:
                diff = abs(int(tg) - student_grade)
                if diff == 1:
                    return 12.0
                if diff == 2:
                    return 6.0
            except (ValueError, TypeError):
                continue
        return 0.0

    def _score_rating(self, avg_rating: float | None) -> float:
        """Return points 0-20 from tutor average rating."""
        if avg_rating is None:
            return 12.0  # new tutors get benefit of the doubt
        return (avg_rating / 5.0) * 20.0

    def _score_style(self, bio: str, headline: str, learning_style: str | None) -> float:
        """Return points 0-15 for learning style compatibility."""
        if not learning_style:
            return _DEFAULT_STYLE_SCORE * 15.0

        keywords = _STYLE_KEYWORDS.get(learning_style.lower(), [])
        if not keywords:
            return _DEFAULT_STYLE_SCORE * 15.0

        combined = (bio + " " + headline).lower()
        hits = sum(1 for kw in keywords if kw in combined)
        ratio = min(hits / max(len(keywords) * 0.3, 1), 1.0)  # 30% hit rate = full score
        # Floor at 0.4 (tutors can be good even if bio doesn't mention style words)
        return max(ratio, 0.4) * 15.0

    def _score_price(self, hourly_rate: float, max_rate: float | None) -> float:
        """Return points 0-10 based on price affordability."""
        if max_rate is None or max_rate <= 0:
            # No budget constraint — score moderately (cheaper tutors get a small bonus)
            if hourly_rate <= 40:
                return 9.0
            if hourly_rate <= 70:
                return 7.0
            if hourly_rate <= 100:
                return 5.0
            return 4.0

        if hourly_rate <= max_rate * 0.7:
            return 10.0
        if hourly_rate <= max_rate:
            # Linear interpolation: at max_rate → 5pts, at 0.7*max_rate → 10pts
            ratio = 1.0 - (hourly_rate - max_rate * 0.7) / (max_rate * 0.3)
            return 5.0 + ratio * 5.0
        # Over budget — partial credit (maybe they can negotiate)
        over_ratio = (hourly_rate - max_rate) / max(max_rate, 1)
        return max(0.0, 5.0 - over_ratio * 10.0)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _get_weak_subjects(self, student_id: int, db: Session) -> list[str]:
        """Return list of subject names where mastery is beginner or developing."""
        try:
            rows = (
                db.query(SubjectMastery.subject_name)
                .filter(
                    SubjectMastery.student_id == student_id,
                    SubjectMastery.mastery_level.in_(["beginner", "developing"]),
                )
                .all()
            )
            return [r.subject_name for r in rows]
        except Exception as exc:
            logger.warning("Could not fetch weak subjects for student %d: %s", student_id, exc)
            return []

    def _get_student_grade(self, student_id: int, db: Session) -> int | None:
        """Return the student's grade level integer, or None."""
        try:
            # First try PersonalizationProfile for cached grade
            profile = (
                db.query(PersonalizationProfile)
                .filter(PersonalizationProfile.student_id == student_id)
                .first()
            )
            if profile:
                # Fallback to Student record for grade_level
                pass

            student = db.query(Student).filter(Student.id == student_id).first()
            return student.grade_level if student else None
        except Exception as exc:
            logger.warning("Could not fetch grade for student %d: %s", student_id, exc)
            return None

    def _get_learning_style(self, student_id: int, db: Session) -> str | None:
        """Return the student's detected learning style string, or None."""
        try:
            profile = (
                db.query(PersonalizationProfile)
                .filter(PersonalizationProfile.student_id == student_id)
                .first()
            )
            return profile.learning_style if profile else None
        except Exception as exc:
            logger.warning("Could not fetch learning style for student %d: %s", student_id, exc)
            return None

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        tutor: TutorProfile,
        covered: list[str],
        weak_subjects: list[str],
        grade_pts: float,
        rating_pts: float,
        style_pts: float,
        price_pts: float,
        learning_style: str | None,
    ) -> str:
        parts: list[str] = []

        # Subject coverage
        if covered:
            parts.append(
                f"Covers {len(covered)}/{len(weak_subjects)} of your weak subjects"
                f" ({', '.join(covered[:3])})"
            )
        elif weak_subjects:
            parts.append("Limited overlap with your weak subjects")
        else:
            parts.append(f"Teaches {', '.join(self._parse_json_list(tutor.subjects)[:2])}")

        # Rating
        if tutor.avg_rating is not None:
            stars = f"{tutor.avg_rating:.1f}-star"
            count = tutor.review_count or 0
            if count > 0:
                parts.append(f"{stars} rated ({count} review{'s' if count != 1 else ''})")
            else:
                parts.append(f"{stars} rated")
        else:
            parts.append("New tutor")

        # Grade match
        if grade_pts >= 20.0:
            parts.append("exact grade level match")
        elif grade_pts >= 12.0:
            parts.append("near grade level match")

        # Learning style
        if style_pts >= 12.0 and learning_style:
            style_label = {
                "visual": "visual learning methods",
                "auditory": "verbal explanation style",
                "reading": "detailed written notes",
                "kinesthetic": "practice-based teaching",
            }.get(learning_style.lower(), "your learning style")
            parts.append(f"teaches via {style_label}")

        # Availability
        available_days = self._parse_json_list(tutor.available_days)
        if available_days:
            parts.append(f"available {tutor.available_hours_start or '16:00'}–{tutor.available_hours_end or '20:00'}")

        return "; ".join(parts[:4]).capitalize() + "."

    @staticmethod
    def _parse_json_list(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            result = json.loads(value)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
