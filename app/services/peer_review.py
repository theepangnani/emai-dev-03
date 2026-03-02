"""Business logic for the Peer Review system.

Handles assignment creation, student submissions, round-robin reviewer
allocation, review submission, teacher-controlled release, and score
aggregation.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.peer_review import (
    PeerReview,
    PeerReviewAllocation,
    PeerReviewAssignment,
    PeerReviewSubmission,
    ReviewStatus,
)
from app.schemas.peer_review import (
    PeerReviewAssignmentCreate,
    PeerReviewSubmissionCreate,
    PeerReviewSummary,
)

if TYPE_CHECKING:
    from app.models.user import User


class PeerReviewService:
    # -----------------------------------------------------------------------
    # Assignment management (teacher)
    # -----------------------------------------------------------------------

    @staticmethod
    def create_assignment(teacher_id: int, data: PeerReviewAssignmentCreate, db: Session) -> PeerReviewAssignment:
        """Create a new peer review assignment owned by the given teacher."""
        rubric_dicts = [c.model_dump() for c in data.rubric] if data.rubric else []
        assignment = PeerReviewAssignment(
            teacher_id=teacher_id,
            course_id=data.course_id,
            title=data.title,
            instructions=data.instructions,
            due_date=data.due_date,
            is_anonymous=data.is_anonymous,
            rubric=rubric_dicts,
            max_reviewers_per_student=data.max_reviewers_per_student,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def list_assignments_for_teacher(teacher_id: int, db: Session) -> list[PeerReviewAssignment]:
        return (
            db.query(PeerReviewAssignment)
            .filter(PeerReviewAssignment.teacher_id == teacher_id)
            .order_by(PeerReviewAssignment.created_at.desc())
            .all()
        )

    @staticmethod
    def list_assignments_for_student(student_user_id: int, db: Session) -> list[PeerReviewAssignment]:
        """Return all peer review assignments (publicly visible to enrolled students).

        Currently returns all assignments; in a course-scoped version this
        would filter by the student's enrolled courses.
        """
        return (
            db.query(PeerReviewAssignment)
            .order_by(PeerReviewAssignment.due_date.asc())
            .all()
        )

    @staticmethod
    def get_assignment(assignment_id: int, db: Session) -> PeerReviewAssignment:
        assignment = db.query(PeerReviewAssignment).filter(
            PeerReviewAssignment.id == assignment_id
        ).first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
        return assignment

    # -----------------------------------------------------------------------
    # Student submission
    # -----------------------------------------------------------------------

    @staticmethod
    def submit_work(
        assignment_id: int,
        student_id: int,
        data: PeerReviewSubmissionCreate,
        db: Session,
    ) -> PeerReviewSubmission:
        """Create or replace the student's submission for this assignment."""
        # Prevent duplicate submissions — update instead
        existing = (
            db.query(PeerReviewSubmission)
            .filter(
                PeerReviewSubmission.assignment_id == assignment_id,
                PeerReviewSubmission.author_id == student_id,
            )
            .first()
        )
        if existing:
            existing.title = data.title
            existing.content = data.content
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

        submission = PeerReviewSubmission(
            assignment_id=assignment_id,
            author_id=student_id,
            title=data.title,
            content=data.content,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return submission

    # -----------------------------------------------------------------------
    # Round-robin allocation
    # -----------------------------------------------------------------------

    @staticmethod
    def allocate_reviewers(assignment_id: int, db: Session) -> list[PeerReviewAllocation]:
        """Auto-assign students to review each other using round-robin.

        Algorithm:
          1. Collect all submission authors for the assignment (shuffle for randomness).
          2. For each author at index i, assign the next N submissions (wrap-around),
             skipping the author's own submission.
          3. Create PeerReviewAllocation records (skip duplicates).
        """
        assignment = PeerReviewService.get_assignment(assignment_id, db)
        submissions = (
            db.query(PeerReviewSubmission)
            .filter(PeerReviewSubmission.assignment_id == assignment_id)
            .all()
        )
        if len(submissions) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Need at least 2 submissions to allocate reviewers",
            )

        n = assignment.max_reviewers_per_student

        # Shuffle for randomness
        shuffled = list(submissions)
        random.shuffle(shuffled)

        new_allocations: list[PeerReviewAllocation] = []
        existing_keys: set[tuple[int, int]] = set()

        # Load existing allocations to avoid duplicates
        for alloc in assignment.allocations:
            existing_keys.add((alloc.reviewer_id, alloc.submission_id))

        for idx, reviewer_sub in enumerate(shuffled):
            reviewer_id = reviewer_sub.author_id
            assigned_count = 0
            offset = 1
            while assigned_count < n and offset < len(shuffled):
                candidate_sub = shuffled[(idx + offset) % len(shuffled)]
                # Skip self-review
                if candidate_sub.author_id != reviewer_id:
                    key = (reviewer_id, candidate_sub.id)
                    if key not in existing_keys:
                        alloc = PeerReviewAllocation(
                            assignment_id=assignment_id,
                            reviewer_id=reviewer_id,
                            submission_id=candidate_sub.id,
                        )
                        db.add(alloc)
                        existing_keys.add(key)
                        new_allocations.append(alloc)
                        assigned_count += 1
                offset += 1

        db.commit()
        return new_allocations

    # -----------------------------------------------------------------------
    # Student reviewing
    # -----------------------------------------------------------------------

    @staticmethod
    def get_my_reviews_to_do(
        student_id: int,
        assignment_id: int,
        db: Session,
    ) -> list[dict]:
        """Return the submissions this student must review, optionally anonymised."""
        assignment = PeerReviewService.get_assignment(assignment_id, db)

        allocations = (
            db.query(PeerReviewAllocation)
            .filter(
                PeerReviewAllocation.assignment_id == assignment_id,
                PeerReviewAllocation.reviewer_id == student_id,
            )
            .all()
        )

        results = []
        for alloc in allocations:
            sub = alloc.submission

            # Check if this review already exists
            review = (
                db.query(PeerReview)
                .filter(
                    PeerReview.submission_id == sub.id,
                    PeerReview.reviewer_id == student_id,
                )
                .first()
            )

            entry: dict = {
                "allocation_id": alloc.id,
                "submission_id": sub.id,
                "submission_title": sub.title,
                "submission_content": sub.content,
                "review_status": review.status if review else ReviewStatus.DRAFT.value,
                "review_id": review.id if review else None,
            }

            if not assignment.is_anonymous:
                entry["author_id"] = sub.author_id

            results.append(entry)

        return results

    @staticmethod
    def submit_review(
        allocation_id: int,
        student_id: int,
        scores: dict,
        feedback: str | None,
        db: Session,
    ) -> PeerReview:
        """Student submits (or updates) a peer review for a given allocation."""
        alloc = db.query(PeerReviewAllocation).filter(
            PeerReviewAllocation.id == allocation_id,
            PeerReviewAllocation.reviewer_id == student_id,
        ).first()
        if not alloc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Allocation not found or not assigned to you",
            )

        assignment = PeerReviewService.get_assignment(alloc.assignment_id, db)

        # Calculate overall score from rubric
        overall: float | None = None
        if scores and assignment.rubric:
            total_points = 0.0
            max_points = 0
            for criterion_def in assignment.rubric:
                key = criterion_def.get("criterion") if isinstance(criterion_def, dict) else criterion_def.criterion
                max_pts = criterion_def.get("max_points") if isinstance(criterion_def, dict) else criterion_def.max_points
                score_val = scores.get(key, 0)
                total_points += float(score_val)
                max_points += int(max_pts)
            if max_points > 0:
                overall = round((total_points / max_points) * 100, 2)

        # Upsert
        existing = (
            db.query(PeerReview)
            .filter(
                PeerReview.submission_id == alloc.submission_id,
                PeerReview.reviewer_id == student_id,
            )
            .first()
        )

        if existing:
            existing.scores = scores
            existing.overall_score = overall
            existing.written_feedback = feedback
            existing.status = ReviewStatus.SUBMITTED.value
            existing.submitted_at = datetime.now(timezone.utc)
            existing.is_anonymous = assignment.is_anonymous
            db.commit()
            db.refresh(existing)
            return existing

        review = PeerReview(
            submission_id=alloc.submission_id,
            reviewer_id=student_id,
            scores=scores,
            overall_score=overall,
            written_feedback=feedback,
            status=ReviewStatus.SUBMITTED.value,
            is_anonymous=assignment.is_anonymous,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    # -----------------------------------------------------------------------
    # Viewing reviews
    # -----------------------------------------------------------------------

    @staticmethod
    def get_submission_reviews(
        submission_id: int,
        requesting_user_id: int,
        db: Session,
    ) -> list[PeerReview]:
        """Return reviews for a submission.

        - Teacher (owner of the assignment) always sees all reviews.
        - The submission author sees reviews only after the teacher releases them.
        - Others are denied.
        """
        submission = db.query(PeerReviewSubmission).filter(
            PeerReviewSubmission.id == submission_id
        ).first()
        if not submission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

        assignment = submission.assignment
        is_teacher = assignment.teacher_id == requesting_user_id
        is_author = submission.author_id == requesting_user_id

        if not is_teacher and not is_author:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if is_author and not assignment.reviews_released:
            return []  # Not released yet

        return (
            db.query(PeerReview)
            .filter(PeerReview.submission_id == submission_id)
            .all()
        )

    # -----------------------------------------------------------------------
    # Teacher actions
    # -----------------------------------------------------------------------

    @staticmethod
    def release_reviews(assignment_id: int, teacher_id: int, db: Session) -> PeerReviewAssignment:
        """Mark all reviews as released so students can see them."""
        assignment = PeerReviewService.get_assignment(assignment_id, db)
        if assignment.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assignment")
        assignment.reviews_released = True
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def get_assignment_summary(
        assignment_id: int,
        teacher_id: int,
        db: Session,
    ) -> list[PeerReviewSummary]:
        """Aggregate scores per submission for the teacher's summary view."""
        assignment = PeerReviewService.get_assignment(assignment_id, db)
        if assignment.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your assignment")

        summaries: list[PeerReviewSummary] = []

        for submission in assignment.submissions:
            scores_calc = PeerReviewService.calculate_scores(submission.id, db)

            # Resolve author name
            from app.models.user import User
            author = db.query(User).filter(User.id == submission.author_id).first()
            author_name = author.full_name if author else f"User {submission.author_id}"

            review_count = (
                db.query(PeerReview)
                .filter(
                    PeerReview.submission_id == submission.id,
                    PeerReview.status == ReviewStatus.SUBMITTED.value,
                )
                .count()
            )

            summaries.append(
                PeerReviewSummary(
                    submission_id=submission.id,
                    author_id=submission.author_id,
                    author_name=author_name,
                    avg_score=scores_calc.get("overall"),
                    review_count=review_count,
                    criteria_averages={
                        k: v for k, v in scores_calc.items() if k != "overall"
                    },
                )
            )

        return summaries

    @staticmethod
    def calculate_scores(submission_id: int, db: Session) -> dict:
        """Calculate average scores per criterion and overall for a submission."""
        reviews = (
            db.query(PeerReview)
            .filter(
                PeerReview.submission_id == submission_id,
                PeerReview.status == ReviewStatus.SUBMITTED.value,
            )
            .all()
        )

        if not reviews:
            return {"overall": None}

        # Aggregate by criterion
        criteria_totals: dict[str, list[float]] = {}
        overall_scores: list[float] = []

        for review in reviews:
            if review.overall_score is not None:
                overall_scores.append(review.overall_score)
            if review.scores:
                for criterion, score in review.scores.items():
                    criteria_totals.setdefault(criterion, []).append(float(score))

        result: dict[str, float | None] = {}
        for criterion, values in criteria_totals.items():
            result[criterion] = round(sum(values) / len(values), 2)

        result["overall"] = (
            round(sum(overall_scores) / len(overall_scores), 2)
            if overall_scores
            else None
        )

        return result
