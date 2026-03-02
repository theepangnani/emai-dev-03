"""Service layer for student goals and milestones."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.student_goal import GoalCategory, GoalStatus, GoalMilestone, StudentGoal
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.student_goal import (
    AIMilestoneSuggestion,
    GoalMilestoneCreate,
    GoalMilestoneUpdate,
    StudentGoalCreate,
    StudentGoalUpdate,
    GoalProgressUpdate,
)

logger = logging.getLogger(__name__)


class StudentGoalService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Helper: resolve student_id from the given user
    # ------------------------------------------------------------------

    def _get_student_id_for_user(self, user: User) -> int:
        """Return the Student.id for a student user, raising 404 if not found."""
        student = self.db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for this user",
            )
        return student.id

    def _assert_goal_owner(self, goal: StudentGoal, user: User) -> None:
        """Raise 403 if user is not the owner of the goal (and not admin)."""
        if user.has_role(UserRole.ADMIN):
            return
        student = self.db.query(Student).filter(Student.user_id == user.id).first()
        if not student or goal.student_id != student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you do not own this goal",
            )

    def _get_goal_or_404(self, goal_id: int) -> StudentGoal:
        goal = self.db.query(StudentGoal).filter(StudentGoal.id == goal_id).first()
        if not goal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Goal {goal_id} not found",
            )
        return goal

    def _get_milestone_or_404(self, milestone_id: int) -> GoalMilestone:
        milestone = self.db.query(GoalMilestone).filter(GoalMilestone.id == milestone_id).first()
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Milestone {milestone_id} not found",
            )
        return milestone

    # ------------------------------------------------------------------
    # Goal CRUD
    # ------------------------------------------------------------------

    def create_goal(self, user: User, data: StudentGoalCreate) -> StudentGoal:
        student_id = self._get_student_id_for_user(user)
        goal = StudentGoal(
            student_id=student_id,
            title=data.title,
            description=data.description,
            category=data.category.value if hasattr(data.category, "value") else data.category,
            target_date=data.target_date,
            status=data.status.value if hasattr(data.status, "value") else data.status,
            progress_pct=data.progress_pct,
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def list_goals(
        self,
        user: User,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[StudentGoal]:
        student_id = self._get_student_id_for_user(user)
        q = self.db.query(StudentGoal).filter(StudentGoal.student_id == student_id)
        if status_filter:
            q = q.filter(StudentGoal.status == status_filter)
        if category_filter:
            q = q.filter(StudentGoal.category == category_filter)
        return q.order_by(StudentGoal.created_at.desc()).all()

    def get_goal(self, goal_id: int, user: User) -> StudentGoal:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)
        return goal

    def update_goal(self, goal_id: int, user: User, data: StudentGoalUpdate) -> StudentGoal:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(value, "value"):
                value = value.value
            setattr(goal, field, value)

        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete_goal(self, goal_id: int, user: User) -> None:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)
        self.db.delete(goal)
        self.db.commit()

    # ------------------------------------------------------------------
    # Progress update
    # ------------------------------------------------------------------

    def update_progress(self, goal_id: int, user: User, data: GoalProgressUpdate) -> StudentGoal:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)

        goal.progress_pct = data.progress_pct
        # Auto-complete goal when progress reaches 100
        if data.progress_pct == 100 and goal.status == GoalStatus.ACTIVE.value:
            goal.status = GoalStatus.COMPLETED.value

        self.db.commit()
        self.db.refresh(goal)
        return goal

    # ------------------------------------------------------------------
    # Milestone CRUD
    # ------------------------------------------------------------------

    def add_milestone(self, goal_id: int, user: User, data: GoalMilestoneCreate) -> GoalMilestone:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)

        milestone = GoalMilestone(
            goal_id=goal_id,
            title=data.title,
            description=data.description,
            target_date=data.target_date,
            display_order=data.display_order,
        )
        self.db.add(milestone)
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def update_milestone(
        self, goal_id: int, milestone_id: int, user: User, data: GoalMilestoneUpdate
    ) -> GoalMilestone:
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)
        milestone = self._get_milestone_or_404(milestone_id)

        if milestone.goal_id != goal_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone does not belong to this goal",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(milestone, field, value)

        # Track completion timestamp
        if "completed" in update_data:
            if update_data["completed"] and not milestone.completed_at:
                milestone.completed_at = datetime.utcnow()
            elif not update_data["completed"]:
                milestone.completed_at = None

        self.db.commit()
        self.db.refresh(milestone)

        # Recalculate goal progress based on milestone completion
        self._recalculate_progress_from_milestones(goal)

        return milestone

    def complete_milestone(self, goal_id: int, milestone_id: int, user: User) -> GoalMilestone:
        """Convenience: mark milestone as completed."""
        data = GoalMilestoneUpdate(completed=True)
        return self.update_milestone(goal_id, milestone_id, user, data)

    def _recalculate_progress_from_milestones(self, goal: StudentGoal) -> None:
        """Update goal progress_pct based on completed milestones ratio."""
        milestones = (
            self.db.query(GoalMilestone).filter(GoalMilestone.goal_id == goal.id).all()
        )
        if not milestones:
            return

        completed_count = sum(1 for m in milestones if m.completed)
        total_count = len(milestones)
        new_pct = int((completed_count / total_count) * 100)
        goal.progress_pct = new_pct

        if new_pct == 100 and goal.status == GoalStatus.ACTIVE.value:
            goal.status = GoalStatus.COMPLETED.value

        self.db.commit()

    # ------------------------------------------------------------------
    # Parent: view child's goals
    # ------------------------------------------------------------------

    def get_parent_child_goals(
        self,
        parent_user: User,
        student_id: int,
        status_filter: Optional[str] = None,
    ) -> List[StudentGoal]:
        """Return goals for a student if the current user is a linked parent."""
        from app.models.student import parent_students

        # Verify parent-child link
        link = (
            self.db.execute(
                parent_students.select().where(
                    (parent_students.c.parent_id == parent_user.id)
                    & (parent_students.c.student_id == student_id)
                )
            ).first()
        )
        if not link and not parent_user.has_role(UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not linked to this student",
            )

        q = self.db.query(StudentGoal).filter(StudentGoal.student_id == student_id)
        if status_filter:
            q = q.filter(StudentGoal.status == status_filter)
        return q.order_by(StudentGoal.created_at.desc()).all()

    # ------------------------------------------------------------------
    # AI milestone generation
    # ------------------------------------------------------------------

    def generate_ai_milestones(
        self, goal_id: int, user: User, save: bool = False
    ) -> List[AIMilestoneSuggestion]:
        """Use GPT-4o-mini to generate 3-5 actionable milestones for a goal."""
        goal = self._get_goal_or_404(goal_id)
        self._assert_goal_owner(goal, user)

        try:
            from openai import OpenAI
            from app.core.config import settings

            client = OpenAI(api_key=settings.openai_api_key)

            today = date.today()
            target_str = str(goal.target_date) if goal.target_date else "no specific deadline"

            prompt = f"""You are an educational coach helping a student break down a goal into achievable milestones.

Goal Title: {goal.title}
Goal Description: {goal.description or "No description provided"}
Category: {goal.category}
Target Completion Date: {target_str}
Today's Date: {today}

Generate 3 to 5 actionable milestones that will help the student achieve this goal.
Each milestone should:
1. Be specific and measurable
2. Be achievable within a reasonable timeframe
3. Build progressively toward the final goal

Return a JSON array with this exact structure:
[
  {{
    "title": "Short milestone title",
    "description": "1-2 sentence description of what to accomplish",
    "suggested_target_date": "YYYY-MM-DD or null"
  }}
]

Space the suggested_target_dates evenly across the timeline from today to the target date.
If no target date is set, suggest dates spread over the next 3 months.
Only return the JSON array, no other text."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            suggestions_data = json.loads(raw)
            suggestions = []
            for item in suggestions_data:
                target_date_val = None
                if item.get("suggested_target_date"):
                    try:
                        target_date_val = date.fromisoformat(item["suggested_target_date"])
                    except (ValueError, TypeError):
                        pass
                suggestions.append(
                    AIMilestoneSuggestion(
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        suggested_target_date=target_date_val,
                    )
                )

            if save:
                for i, suggestion in enumerate(suggestions):
                    milestone = GoalMilestone(
                        goal_id=goal_id,
                        title=suggestion.title,
                        description=suggestion.description,
                        target_date=suggestion.suggested_target_date,
                        display_order=i,
                    )
                    self.db.add(milestone)
                self.db.commit()

            return suggestions

        except Exception as exc:
            logger.error("Failed to generate AI milestones for goal %d: %s", goal_id, exc)
            # Return sensible fallback milestones
            return self._fallback_milestones(goal)

    def _fallback_milestones(self, goal: StudentGoal) -> List[AIMilestoneSuggestion]:
        """Return generic milestone suggestions when AI is unavailable."""
        today = date.today()
        delta = timedelta(days=30)
        return [
            AIMilestoneSuggestion(
                title="Define the plan",
                description="Break down your goal into specific actions and write them down.",
                suggested_target_date=today + delta,
            ),
            AIMilestoneSuggestion(
                title="Complete initial steps",
                description="Take the first concrete actions toward your goal.",
                suggested_target_date=today + delta * 2,
            ),
            AIMilestoneSuggestion(
                title="Review progress",
                description="Evaluate how far you've come and adjust your approach if needed.",
                suggested_target_date=today + delta * 3,
            ),
        ]
