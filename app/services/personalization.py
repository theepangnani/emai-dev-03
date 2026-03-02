"""PersonalizationEngine — Advanced AI Personalization (Phase 3).

Computes subject mastery scores, recommends adaptive difficulty levels, detects
learning style via AI, and generates personalised study recommendations.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.analytics import GradeRecord
from app.models.course import Course
from app.models.personalization import (
    AdaptiveDifficulty,
    LearningStyle,
    PersonalizationProfile,
    SubjectMastery,
)
from app.models.quiz_result import QuizResult
from app.models.report_card import ReportCard
from app.models.student import Student
from app.models.study_guide import StudyGuide
from app.models.user import User

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

_DIFFICULTY_ORDER = ["easy", "medium", "hard"]

def _mastery_level(score: float) -> str:
    if score >= 80:
        return "advanced"
    if score >= 60:
        return "proficient"
    if score >= 40:
        return "developing"
    return "beginner"


# ────────────────────────────────────────────────────────────────────────────
# Engine
# ────────────────────────────────────────────────────────────────────────────


class PersonalizationEngine:
    """Stateless engine — all state lives in the database."""

    # ------------------------------------------------------------------
    # Profile helpers
    # ------------------------------------------------------------------

    def get_or_create_profile(self, student_id: int, db: Session) -> PersonalizationProfile:
        """Return the profile for *student_id*, creating a blank one if absent."""
        profile = (
            db.query(PersonalizationProfile)
            .filter(PersonalizationProfile.student_id == student_id)
            .first()
        )
        if profile is None:
            profile = PersonalizationProfile(student_id=student_id)
            db.add(profile)
            db.flush()
        return profile

    # ------------------------------------------------------------------
    # Mastery computation
    # ------------------------------------------------------------------

    def compute_mastery(self, student_id: int, db: Session) -> list[SubjectMastery]:
        """Aggregate quiz, grade and report-card data into SubjectMastery rows.

        Formula per subject:
            mastery_score = quiz_avg * 0.4  +  grade_avg * 0.4  +  study_freq_score * 0.2

        Trend uses last-3 vs first-3 quiz scores (requires >= 6 data points).
        Returns the upserted list of SubjectMastery records.
        """
        # ---- 1. Quiz data grouped by study-guide course ----
        # QuizResult links to StudyGuide which links to Course.
        quiz_rows = (
            db.query(
                Course.id.label("course_id"),
                Course.name.label("course_name"),
                Course.subject.label("subject"),
                sa_func.avg(QuizResult.percentage).label("quiz_avg"),
                sa_func.count(QuizResult.id).label("quiz_count"),
                sa_func.max(QuizResult.completed_at).label("last_quiz_date"),
            )
            .join(StudyGuide, StudyGuide.course_id == Course.id)
            .join(QuizResult, QuizResult.study_guide_id == StudyGuide.id)
            .join(User, User.id == QuizResult.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(Student.id == student_id)
            .group_by(Course.id, Course.name, Course.subject)
            .all()
        )

        # ---- 2. Grade data from grade_records ----
        grade_rows = (
            db.query(
                Course.id.label("course_id"),
                Course.name.label("course_name"),
                Course.subject.label("subject"),
                sa_func.avg(GradeRecord.percentage).label("grade_avg"),
            )
            .join(GradeRecord, GradeRecord.course_id == Course.id)
            .filter(GradeRecord.student_id == student_id)
            .group_by(Course.id, Course.name, Course.subject)
            .all()
        )

        # ---- 3. Report-card subject marks ----
        rc_subject_avgs: dict[str, float] = {}
        report_cards = (
            db.query(ReportCard)
            .filter(
                ReportCard.student_id == student_id,
                ReportCard.status == "analyzed",
            )
            .all()
        )
        for rc in report_cards:
            marks = rc.extracted_marks or []
            for mark in marks:
                subj = str(mark.get("subject", "")).strip()
                pct = mark.get("percentage")
                if subj and pct is not None:
                    try:
                        pct_val = float(pct)
                        if subj not in rc_subject_avgs:
                            rc_subject_avgs[subj] = []  # type: ignore[assignment]
                        rc_subject_avgs[subj].append(pct_val)  # type: ignore[index]
                    except (ValueError, TypeError):
                        pass
        rc_subject_avgs_final: dict[str, float] = {
            k: sum(v) / len(v)  # type: ignore[arg-type]
            for k, v in rc_subject_avgs.items()  # type: ignore[union-attr]
        }

        # ---- 4. Study frequency per course ----
        sg_counts = (
            db.query(
                StudyGuide.course_id.label("course_id"),
                sa_func.count(StudyGuide.id).label("sg_count"),
            )
            .join(User, User.id == StudyGuide.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(
                Student.id == student_id,
                StudyGuide.course_id.isnot(None),
            )
            .group_by(StudyGuide.course_id)
            .all()
        )
        max_sg = max((r.sg_count for r in sg_counts), default=1) or 1
        sg_freq_by_course: dict[int, float] = {
            r.course_id: (r.sg_count / max_sg) * 100 for r in sg_counts
        }

        # ---- 5. Merge all subjects ----
        subjects: dict[str, dict] = {}

        for row in quiz_rows:
            key = str(row.course_id)
            subjects.setdefault(key, {
                "course_id": row.course_id,
                "subject_code": row.subject or row.course_name,
                "subject_name": row.course_name,
            })
            subjects[key]["quiz_avg"] = float(row.quiz_avg or 0)
            subjects[key]["quiz_count"] = int(row.quiz_count or 0)
            subjects[key]["last_quiz_date"] = row.last_quiz_date

        for row in grade_rows:
            key = str(row.course_id)
            subjects.setdefault(key, {
                "course_id": row.course_id,
                "subject_code": row.subject or row.course_name,
                "subject_name": row.course_name,
            })
            subjects[key]["grade_avg"] = float(row.grade_avg or 0)

        # Add report card subjects that may not have courses
        for subj_name, avg in rc_subject_avgs_final.items():
            # Try to match to an existing course key by name
            matched = False
            for key, data in subjects.items():
                if data["subject_name"].lower() == subj_name.lower():
                    subjects[key].setdefault("grade_avg", 0.0)
                    # blend report card avg into grade_avg
                    existing = subjects[key]["grade_avg"]
                    subjects[key]["grade_avg"] = (existing + avg) / 2
                    matched = True
                    break
            if not matched:
                rc_key = f"rc_{subj_name}"
                subjects[rc_key] = {
                    "course_id": None,
                    "subject_code": subj_name,
                    "subject_name": subj_name,
                    "grade_avg": avg,
                }

        # ---- 6. Trend: last-3 vs first-3 quiz scores per course ----
        trends: dict[str, str] = {}
        for key, data in subjects.items():
            cid = data.get("course_id")
            if cid is None:
                continue
            quiz_scores = (
                db.query(QuizResult.percentage, QuizResult.completed_at)
                .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
                .join(User, User.id == QuizResult.user_id)
                .join(Student, Student.user_id == User.id)
                .filter(
                    Student.id == student_id,
                    StudyGuide.course_id == cid,
                )
                .order_by(QuizResult.completed_at.asc())
                .all()
            )
            if len(quiz_scores) >= 6:
                first3 = sum(r.percentage for r in quiz_scores[:3]) / 3
                last3 = sum(r.percentage for r in quiz_scores[-3:]) / 3
                if last3 > first3 + 5:
                    trends[key] = "improving"
                elif last3 < first3 - 5:
                    trends[key] = "declining"
                else:
                    trends[key] = "stable"
            else:
                trends[key] = "stable"

        # ---- 7. Compute mastery scores and upsert ----
        results: list[SubjectMastery] = []

        for key, data in subjects.items():
            quiz_avg = data.get("quiz_avg", 0.0)
            grade_avg = data.get("grade_avg", 0.0)
            cid = data.get("course_id")
            study_freq_score = sg_freq_by_course.get(cid, 0.0) if cid else 0.0

            mastery_score = round(
                quiz_avg * 0.4 + grade_avg * 0.4 + study_freq_score * 0.2, 1
            )

            level = _mastery_level(mastery_score)
            trend = trends.get(key, "stable")
            next_topics = self.recommend_next_topics_from_level(level, data["subject_name"])

            # Upsert
            existing = (
                db.query(SubjectMastery)
                .filter(
                    SubjectMastery.student_id == student_id,
                    SubjectMastery.subject_code == data["subject_code"],
                )
                .first()
            )
            if existing is None:
                existing = SubjectMastery(
                    student_id=student_id,
                    subject_code=data["subject_code"],
                )
                db.add(existing)

            existing.subject_name = data["subject_name"]
            existing.mastery_score = mastery_score
            existing.mastery_level = level
            existing.quiz_score_avg = round(quiz_avg, 1)
            existing.quiz_attempts = data.get("quiz_count", 0)
            existing.grade_avg = round(grade_avg, 1)
            existing.last_quiz_date = data.get("last_quiz_date")
            existing.trend = trend
            existing.recommended_next_topics = json.dumps(next_topics)

            results.append(existing)

        db.flush()

        # Update profile strong/weak subjects
        if results:
            sorted_by_score = sorted(results, key=lambda m: m.mastery_score, reverse=True)
            strong = [m.subject_code for m in sorted_by_score if m.mastery_score >= 60][:3]
            weak = [m.subject_code for m in reversed(sorted_by_score) if m.mastery_score < 60][:3]
            profile = self.get_or_create_profile(student_id, db)
            profile.strong_subjects = json.dumps(strong)
            profile.weak_subjects = json.dumps(weak)
            db.flush()

        return results

    # ------------------------------------------------------------------
    # Adaptive difficulty
    # ------------------------------------------------------------------

    def recommend_difficulty(
        self, student_id: int, subject_code: str, content_type: str, db: Session
    ) -> str:
        """Return recommended difficulty based on consecutive correct/incorrect streak."""
        record = (
            db.query(AdaptiveDifficulty)
            .filter(
                AdaptiveDifficulty.student_id == student_id,
                AdaptiveDifficulty.subject_code == subject_code,
                AdaptiveDifficulty.content_type == content_type,
            )
            .first()
        )
        if record is None:
            return "medium"

        current_idx = _DIFFICULTY_ORDER.index(record.current_difficulty)

        if record.consecutive_correct >= 3:
            new_idx = min(current_idx + 1, len(_DIFFICULTY_ORDER) - 1)
            return _DIFFICULTY_ORDER[new_idx]

        if record.consecutive_incorrect >= 2:
            new_idx = max(current_idx - 1, 0)
            return _DIFFICULTY_ORDER[new_idx]

        return record.current_difficulty

    def update_difficulty_after_attempt(
        self,
        student_id: int,
        subject_code: str,
        content_type: str,
        passed: bool,
        db: Session,
    ) -> AdaptiveDifficulty:
        """Update consecutive counts and apply difficulty adjustment."""
        record = (
            db.query(AdaptiveDifficulty)
            .filter(
                AdaptiveDifficulty.student_id == student_id,
                AdaptiveDifficulty.subject_code == subject_code,
                AdaptiveDifficulty.content_type == content_type,
            )
            .first()
        )
        if record is None:
            record = AdaptiveDifficulty(
                student_id=student_id,
                subject_code=subject_code,
                content_type=content_type,
            )
            db.add(record)

        record.total_attempts += 1

        if passed:
            record.consecutive_correct += 1
            record.consecutive_incorrect = 0
        else:
            record.consecutive_incorrect += 1
            record.consecutive_correct = 0

        # Apply difficulty adjustment
        current_idx = _DIFFICULTY_ORDER.index(record.current_difficulty)
        if record.consecutive_correct >= 3:
            new_idx = min(current_idx + 1, len(_DIFFICULTY_ORDER) - 1)
            record.current_difficulty = _DIFFICULTY_ORDER[new_idx]
            if new_idx != current_idx:
                record.consecutive_correct = 0  # reset after upgrade
        elif record.consecutive_incorrect >= 2:
            new_idx = max(current_idx - 1, 0)
            record.current_difficulty = _DIFFICULTY_ORDER[new_idx]
            if new_idx != current_idx:
                record.consecutive_incorrect = 0  # reset after downgrade

        db.flush()
        return record

    # ------------------------------------------------------------------
    # Learning style detection (AI)
    # ------------------------------------------------------------------

    async def detect_learning_style(
        self, student_id: int, db: Session
    ) -> tuple[LearningStyle, float]:
        """Use Claude to detect learning style from behavioural evidence.

        Evidence gathered:
        - Study guide vs quiz vs flashcard generation counts
        - Average session length (approximated from time_taken_seconds)
        - Time-of-day distribution of quiz attempts
        - Total quiz vs flashcard preference
        """
        from app.services.ai_service import generate_content

        # ---- Gather evidence ----
        sg_by_type = (
            db.query(StudyGuide.guide_type, sa_func.count(StudyGuide.id).label("cnt"))
            .join(User, User.id == StudyGuide.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(Student.id == student_id)
            .group_by(StudyGuide.guide_type)
            .all()
        )
        type_counts = {r.guide_type: r.cnt for r in sg_by_type}

        quiz_results = (
            db.query(QuizResult.time_taken_seconds, QuizResult.completed_at)
            .join(User, User.id == QuizResult.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(Student.id == student_id)
            .limit(50)
            .all()
        )

        avg_time = None
        hour_counts: dict[int, int] = {}
        if quiz_results:
            times = [r.time_taken_seconds for r in quiz_results if r.time_taken_seconds]
            avg_time = sum(times) / len(times) if times else None
            for r in quiz_results:
                if r.completed_at:
                    h = r.completed_at.hour
                    hour_counts[h] = hour_counts.get(h, 0) + 1

        preferred_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None  # type: ignore[arg-type]

        evidence_text = f"""
Student ID: {student_id}
Study guide counts by type:
- study_guide: {type_counts.get('study_guide', 0)}
- quiz: {type_counts.get('quiz', 0)}
- flashcards: {type_counts.get('flashcards', 0)}
Average quiz time (seconds): {avg_time or 'unknown'}
Most active hour of day (0-23): {preferred_hour if preferred_hour is not None else 'unknown'}
Total quiz attempts: {len(quiz_results)}
"""

        prompt = f"""Analyze this K-12 student's study behaviour and detect their dominant learning style.

{evidence_text}

Learning style definitions:
- visual: prefers diagrams, charts, visual examples
- auditory: prefers explanations, verbal reasoning, discussion
- reading: prefers text, detailed notes, written study guides
- kinesthetic: prefers practice, hands-on exercises, flashcards

Rules for classification:
- High flashcard count + short quiz times → kinesthetic
- High study_guide count + long quiz times → reading
- High quiz count + varied hours → auditory
- Mixed but visual heavy → visual

Respond with a JSON object only (no markdown):
{{"learning_style": "<visual|auditory|reading|kinesthetic>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}
"""

        try:
            raw = await generate_content(
                prompt,
                system_prompt=(
                    "You are an educational data analyst. "
                    "Return only valid JSON with no markdown fences."
                ),
                max_tokens=200,
                temperature=0.2,
            )
            # Strip any accidental markdown fences
            clean = raw.strip().strip("```json").strip("```").strip()
            data = json.loads(clean)
            style_str = data.get("learning_style", "reading").lower()
            confidence = float(data.get("confidence", 0.5))

            # Validate the style
            try:
                style = LearningStyle(style_str)
            except ValueError:
                style = LearningStyle.READING
                confidence = 0.3

            return style, min(max(confidence, 0.0), 1.0)

        except Exception as exc:
            logger.warning("Learning style detection failed: %s", exc)
            return LearningStyle.READING, 0.3

    # ------------------------------------------------------------------
    # AI study recommendations
    # ------------------------------------------------------------------

    async def generate_study_recommendations(
        self, student_id: int, db: Session
    ) -> dict:
        """Generate personalised study recommendations using AI.

        Returns a dict with keys:
            weak_areas, recommended_topics, study_schedule,
            preferred_format, difficulty_adjustment
        """
        from app.services.ai_service import generate_content

        # Gather mastery data
        masteries = (
            db.query(SubjectMastery)
            .filter(SubjectMastery.student_id == student_id)
            .all()
        )

        profile = self.get_or_create_profile(student_id, db)

        mastery_summary = "\n".join(
            f"- {m.subject_name}: {m.mastery_score:.0f}% ({m.mastery_level}, trend: {m.trend})"
            for m in masteries
        ) or "No mastery data yet."

        prompt = f"""Generate personalised study recommendations for a K-12 student.

Student profile:
- Learning style: {profile.learning_style or 'unknown'}
- Preferred difficulty: {profile.preferred_difficulty}
- Session length: {profile.study_session_length} minutes
- Preferred study time: {profile.preferred_study_time}

Subject mastery:
{mastery_summary}

Produce a JSON object (no markdown fences) with exactly these keys:
{{
  "weak_areas": ["<subject or topic>", ...],
  "recommended_topics": ["<specific topic to study next>", ...],
  "study_schedule": {{
    "Monday": "<brief suggestion>",
    "Tuesday": "<brief suggestion>",
    "Wednesday": "<brief suggestion>",
    "Thursday": "<brief suggestion>",
    "Friday": "<brief suggestion>",
    "Saturday": "<brief suggestion>",
    "Sunday": "<brief suggestion>"
  }},
  "preferred_format": "<flashcards|study_guides|quizzes>",
  "difficulty_adjustment": "<increase|maintain|decrease>",
  "summary": "<2 sentence personalized summary>"
}}
"""

        try:
            raw = await generate_content(
                prompt,
                system_prompt=(
                    "You are a K-12 educational advisor. "
                    "Return only valid JSON with no markdown fences."
                ),
                max_tokens=800,
                temperature=0.4,
            )
            clean = raw.strip().strip("```json").strip("```").strip()
            return json.loads(clean)
        except Exception as exc:
            logger.warning("Study recommendations generation failed: %s", exc)
            weak = [m.subject_name for m in masteries if m.mastery_score < 60]
            return {
                "weak_areas": weak,
                "recommended_topics": weak[:3],
                "study_schedule": {
                    day: f"Review {weak[0] if weak else 'your subjects'}"
                    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                },
                "preferred_format": "study_guides",
                "difficulty_adjustment": "maintain",
                "summary": "Keep up with your studies and focus on weaker subjects.",
            }

    # ------------------------------------------------------------------
    # Rule-based next topic suggestions
    # ------------------------------------------------------------------

    def recommend_next_topics(self, mastery: SubjectMastery) -> list[str]:
        """Rule-based next topic suggestions based on mastery level."""
        return self.recommend_next_topics_from_level(mastery.mastery_level, mastery.subject_name)

    @staticmethod
    def recommend_next_topics_from_level(level: str, subject_name: str) -> list[str]:
        """Return simple level-appropriate topic suggestions."""
        subject = subject_name.lower()

        templates: dict[str, dict[str, list[str]]] = {
            "math": {
                "beginner": ["Basic arithmetic review", "Number patterns", "Introduction to fractions"],
                "developing": ["Algebra fundamentals", "Geometry basics", "Fraction operations"],
                "proficient": ["Quadratic equations", "Trigonometry", "Statistics"],
                "advanced": ["Calculus introduction", "Vectors", "Complex problem solving"],
            },
            "science": {
                "beginner": ["Scientific method", "Basic biology", "Matter and energy"],
                "developing": ["Cell biology", "Chemical reactions", "Forces and motion"],
                "proficient": ["Genetics", "Chemical bonding", "Waves and optics"],
                "advanced": ["Molecular biology", "Thermodynamics", "Quantum concepts"],
            },
            "english": {
                "beginner": ["Reading comprehension", "Grammar basics", "Sentence structure"],
                "developing": ["Essay writing", "Literary analysis", "Vocabulary building"],
                "proficient": ["Critical analysis", "Research writing", "Rhetoric"],
                "advanced": ["Literary theory", "Advanced composition", "Comparative literature"],
            },
            "history": {
                "beginner": ["Timeline skills", "Primary sources", "Key historical events"],
                "developing": ["Cause and effect", "Historical perspectives", "Document analysis"],
                "proficient": ["Historiography", "Comparative history", "Thematic analysis"],
                "advanced": ["Historical debate", "Original research", "Global connections"],
            },
        }

        for key, by_level in templates.items():
            if key in subject:
                return by_level.get(level, by_level["developing"])

        # Generic fallback
        generic: dict[str, list[str]] = {
            "beginner": [f"{subject_name} fundamentals", "Review core concepts", "Build foundational skills"],
            "developing": [f"Intermediate {subject_name}", "Practice problem sets", "Concept reinforcement"],
            "proficient": [f"Advanced {subject_name} topics", "Application exercises", "Analytical thinking"],
            "advanced": [f"Expert {subject_name}", "Independent projects", "Cross-subject connections"],
        }
        return generic.get(level, generic["developing"])
