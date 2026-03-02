"""GradePredictionService — AI-powered grade trajectory prediction engine.

Algorithm:
  1. Gather quiz scores (via QuizResult → StudyGuide → Course), assignment grades,
     study frequency, and subject mastery when available.
  2. Compute weighted baseline: quiz_avg * 0.45 + assignment_avg * 0.40 + study_freq * 0.15
  3. Determine trend: last-3 vs previous-3 quiz scores (>5 pts difference triggers label change)
  4. Confidence: 0.5 + min(data_points * 0.05, 0.4)
  5. Ask GPT-4o-mini for 3–5 human-readable factor bullet points
  6. Upsert GradePrediction record, return response
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.grade_prediction import GradePrediction
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User
from app.schemas.grade_prediction import GradePredictionListResponse, GradePredictionResponse

logger = logging.getLogger(__name__)


class GradePredictionService:
    """Stateless service — all state lives in the database."""

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------

    async def predict_grade(
        self,
        student_user_id: int,
        db: Session,
        course_id: Optional[int] = None,
    ) -> List[GradePredictionResponse]:
        """Generate grade predictions for a student.

        If *course_id* is provided, only that course is predicted.
        Otherwise, predictions are generated for every enrolled course.

        Returns the list of newly stored GradePrediction responses.
        """
        # Resolve Student record
        student = db.query(Student).filter(Student.user_id == student_user_id).first()
        if not student:
            return []

        # Determine courses to predict
        if course_id is not None:
            courses = db.query(Course).filter(Course.id == course_id).all()
        else:
            courses = (
                db.query(Course)
                .join(student_courses, student_courses.c.course_id == Course.id)
                .filter(student_courses.c.student_id == student.id)
                .all()
            )

        # If no enrolled courses, still produce one overall prediction
        if not courses:
            result = await self._predict_single(student, None, db)
            if result:
                return [result]
            return []

        results = []
        for course in courses:
            pred = await self._predict_single(student, course, db)
            if pred:
                results.append(pred)

        return results

    async def _predict_single(
        self,
        student: Student,
        course: Optional[Course],
        db: Session,
    ) -> Optional[GradePredictionResponse]:
        """Generate one prediction for a student / course pair."""
        course_id = course.id if course else None
        course_name = course.name if course else None

        # ---- 1. Quiz data ----
        quiz_query = (
            db.query(QuizResult.percentage, QuizResult.completed_at)
            .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
            .join(User, User.id == QuizResult.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(Student.id == student.id)
        )
        if course_id:
            quiz_query = quiz_query.filter(StudyGuide.course_id == course_id)

        quiz_rows = quiz_query.order_by(QuizResult.completed_at.asc()).all()
        quiz_scores = [float(r.percentage) for r in quiz_rows]
        quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0.0

        # ---- 2. Assignment / grade data ----
        assign_query = (
            db.query(StudentAssignment.grade, Assignment.max_points)
            .join(Assignment, Assignment.id == StudentAssignment.assignment_id)
            .filter(StudentAssignment.student_id == student.id)
            .filter(StudentAssignment.grade.isnot(None))
            .filter(Assignment.max_points.isnot(None))
            .filter(Assignment.max_points > 0)
        )
        if course_id:
            assign_query = assign_query.filter(Assignment.course_id == course_id)

        assign_rows = assign_query.all()
        if assign_rows:
            assignment_avg = sum(
                (r.grade / r.max_points) * 100.0 for r in assign_rows
            ) / len(assign_rows)
        else:
            assignment_avg = 0.0

        # ---- 3. Study frequency (last 30 days) ----
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sg_query = (
            db.query(sa_func.count(StudyGuide.id))
            .join(User, User.id == StudyGuide.user_id)
            .join(Student, Student.user_id == User.id)
            .filter(Student.id == student.id)
            .filter(StudyGuide.created_at >= thirty_days_ago)
        )
        if course_id:
            sg_query = sg_query.filter(StudyGuide.course_id == course_id)

        study_guide_count = sg_query.scalar() or 0
        study_freq_score = min(study_guide_count * 5, 30)  # cap at 30

        # ---- 4. Subject mastery (optional bonus signal) ----
        mastery_bonus = 0.0
        try:
            from app.models.personalization import SubjectMastery
            if course and course.subject:
                mastery = (
                    db.query(SubjectMastery)
                    .filter(
                        SubjectMastery.student_id == student.id,
                        SubjectMastery.subject_code == (course.subject or course.name),
                    )
                    .first()
                )
                if mastery:
                    mastery_bonus = mastery.mastery_score * 0.05  # very small signal
        except Exception:
            pass

        # ---- 5. Weighted baseline ----
        # When we have no quiz/assignment data, use study freq only
        data_points = len(quiz_scores) + len(assign_rows)

        if data_points == 0:
            # Fall back: assume neutral baseline from study freq
            weighted = 50.0 + study_freq_score
        else:
            q_weight = 0.45 if quiz_scores else 0.0
            a_weight = 0.40 if assign_rows else 0.0
            s_weight = 0.15
            normalizer = q_weight + a_weight + s_weight
            weighted = (
                quiz_avg * q_weight
                + assignment_avg * a_weight
                + study_freq_score * s_weight
            ) / normalizer * (1 / 0.15) * s_weight + (
                quiz_avg * q_weight + assignment_avg * a_weight
            )
            # Simpler formula
            weighted = quiz_avg * 0.45 + assignment_avg * 0.40 + study_freq_score * 0.15

        predicted_grade = min(max(round(weighted + mastery_bonus, 1), 0.0), 100.0)

        # ---- 6. Trend ----
        trend = "stable"
        if len(quiz_scores) >= 6:
            first3_avg = sum(quiz_scores[:3]) / 3
            last3_avg = sum(quiz_scores[-3:]) / 3
            if last3_avg > first3_avg + 5:
                trend = "improving"
            elif last3_avg < first3_avg - 5:
                trend = "declining"

        # ---- 7. Confidence ----
        confidence = round(min(0.5 + data_points * 0.05, 0.9), 2)

        # ---- 8. AI factors ----
        factors = await self._generate_factors(
            student=student,
            course_name=course_name,
            predicted_grade=predicted_grade,
            quiz_avg=quiz_avg,
            quiz_count=len(quiz_scores),
            assignment_avg=assignment_avg,
            assignment_count=len(assign_rows),
            study_guide_count=study_guide_count,
            trend=trend,
            confidence=confidence,
        )

        # ---- 9. Upsert prediction ----
        today = date.today()
        existing = (
            db.query(GradePrediction)
            .filter(
                GradePrediction.student_id == student.user_id,
                GradePrediction.course_id == course_id,
                GradePrediction.prediction_date == today,
            )
            .first()
        )
        if existing is None:
            existing = GradePrediction(
                student_id=student.user_id,
                course_id=course_id,
                prediction_date=today,
            )
            db.add(existing)

        existing.predicted_grade = predicted_grade
        existing.confidence = confidence
        existing.trend = trend
        existing.factors = factors

        try:
            db.commit()
            db.refresh(existing)
        except Exception as e:
            db.rollback()
            logger.warning("Failed to upsert GradePrediction: %s", e)
            existing.id = 0  # sentinel

        return GradePredictionResponse(
            id=existing.id,
            student_id=existing.student_id,
            course_id=course_id,
            course_name=course_name,
            predicted_grade=predicted_grade,
            confidence=confidence,
            trend=trend,
            factors=factors,
            prediction_date=today,
            created_at=existing.created_at or datetime.utcnow(),
        )

    async def _generate_factors(
        self,
        *,
        student: Student,
        course_name: Optional[str],
        predicted_grade: float,
        quiz_avg: float,
        quiz_count: int,
        assignment_avg: float,
        assignment_count: int,
        study_guide_count: int,
        trend: str,
        confidence: float,
    ) -> List[str]:
        """Ask GPT-4o-mini for 3–5 human-readable explanation bullets."""
        from app.services.ai_service import generate_content

        subject_label = course_name or "all courses"
        prompt = f"""You are an educational data analyst. A K-12 student has a predicted grade of {predicted_grade:.1f}% for {subject_label}.

Data summary:
- Quiz average: {quiz_avg:.1f}% across {quiz_count} quiz(zes)
- Assignment average: {assignment_avg:.1f}% across {assignment_count} assignment(s)
- Study materials created in last 30 days: {study_guide_count}
- Grade trend: {trend}
- Prediction confidence: {confidence:.0%}

Generate exactly 3 to 5 concise bullet points (plain strings, no markdown) explaining the key factors behind this prediction. Each bullet should be a single sentence, starting with the factor name.

Return ONLY a JSON array of strings, e.g.:
["Quiz performance of 82% demonstrates strong mastery.", "Regular study activity (5 materials) boosts engagement."]
"""
        try:
            raw = await generate_content(
                prompt,
                system_prompt="You are an educational data analyst. Return only a JSON array of plain-text strings. No markdown.",
                max_tokens=400,
                temperature=0.3,
            )
            clean = raw.strip().strip("```json").strip("```").strip()
            data = json.loads(clean)
            if isinstance(data, list):
                return [str(s) for s in data[:5]]
        except Exception as exc:
            logger.warning("Grade prediction factor generation failed: %s", exc)

        # Fallback rules-based factors
        factors: List[str] = []
        if quiz_count > 0:
            factors.append(
                f"Quiz average of {quiz_avg:.0f}% {'indicates strong understanding' if quiz_avg >= 70 else 'suggests areas for improvement'}."
            )
        if assignment_count > 0:
            factors.append(
                f"Assignment completion rate averages {assignment_avg:.0f}%, {'showing consistent effort' if assignment_avg >= 70 else 'indicating missed or low-scoring submissions'}."
            )
        if study_guide_count > 0:
            factors.append(
                f"Active study habits: {study_guide_count} study material(s) created in the last 30 days."
            )
        if trend != "stable":
            label = "upward" if trend == "improving" else "downward"
            factors.append(f"Recent quiz scores show a {label} trend.")
        if not factors:
            factors.append("Insufficient data — prediction is based on baseline estimation.")
            factors.append("Complete more quizzes and assignments to improve prediction accuracy.")

        return factors

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_predictions(self, student_user_id: int, db: Session) -> GradePredictionListResponse:
        """Return the most recent prediction per course for a student."""
        # Sub-query: max created_at per (student_id, course_id)
        latest_subq = (
            db.query(
                GradePrediction.course_id,
                sa_func.max(GradePrediction.created_at).label("max_created"),
            )
            .filter(GradePrediction.student_id == student_user_id)
            .group_by(GradePrediction.course_id)
            .subquery()
        )

        rows = (
            db.query(GradePrediction)
            .join(
                latest_subq,
                (GradePrediction.course_id == latest_subq.c.course_id)
                & (GradePrediction.created_at == latest_subq.c.max_created),
            )
            .filter(GradePrediction.student_id == student_user_id)
            .all()
        )

        # Fetch course names
        course_map: dict[int, str] = {}
        for row in rows:
            if row.course_id and row.course_id not in course_map:
                c = db.query(Course).filter(Course.id == row.course_id).first()
                if c:
                    course_map[row.course_id] = c.name

        predictions = [
            GradePredictionResponse(
                id=r.id,
                student_id=r.student_id,
                course_id=r.course_id,
                course_name=course_map.get(r.course_id) if r.course_id else None,
                predicted_grade=r.predicted_grade,
                confidence=r.confidence,
                trend=r.trend,
                factors=r.factors or [],
                prediction_date=r.prediction_date,
                created_at=r.created_at,
            )
            for r in rows
        ]

        # Summary metrics
        overall_gpa: Optional[float] = None
        strongest: Optional[str] = None
        at_risk: Optional[str] = None
        if predictions:
            grades = [p.predicted_grade for p in predictions]
            overall_gpa = round(sum(grades) / len(grades), 1)
            best = max(predictions, key=lambda p: p.predicted_grade)
            worst = min(predictions, key=lambda p: p.predicted_grade)
            strongest = best.course_name
            if worst.predicted_grade < 60:
                at_risk = worst.course_name

        return GradePredictionListResponse(
            predictions=predictions,
            overall_gpa_prediction=overall_gpa,
            strongest_course=strongest,
            at_risk_course=at_risk,
        )

    def get_course_prediction(
        self, student_user_id: int, course_id: int, db: Session
    ) -> Optional[GradePredictionResponse]:
        """Return the latest prediction for a specific course."""
        row = (
            db.query(GradePrediction)
            .filter(
                GradePrediction.student_id == student_user_id,
                GradePrediction.course_id == course_id,
            )
            .order_by(GradePrediction.created_at.desc())
            .first()
        )
        if not row:
            return None

        course_name: Optional[str] = None
        if row.course_id:
            c = db.query(Course).filter(Course.id == row.course_id).first()
            course_name = c.name if c else None

        return GradePredictionResponse(
            id=row.id,
            student_id=row.student_id,
            course_id=row.course_id,
            course_name=course_name,
            predicted_grade=row.predicted_grade,
            confidence=row.confidence,
            trend=row.trend,
            factors=row.factors or [],
            prediction_date=row.prediction_date,
            created_at=row.created_at,
        )

    def get_parent_predictions(
        self, parent_user_id: int, student_user_id: int, db: Session
    ) -> Optional[GradePredictionListResponse]:
        """Verify parent-child link, then return child predictions."""
        student = db.query(Student).filter(Student.user_id == student_user_id).first()
        if not student:
            return None

        # Check parent link via parent_students join table
        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == parent_user_id,
                parent_students.c.student_id == student.id,
            )
            .first()
        )
        if not link:
            return None

        return self.get_predictions(student_user_id, db)
