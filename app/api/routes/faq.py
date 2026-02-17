from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.faq import FAQQuestion, FAQAnswer, FAQAnswerStatus, FAQQuestionStatus
from app.models.notification import Notification, NotificationType
from app.api.deps import get_current_user, require_role
from app.schemas.faq import (
    FAQQuestionCreate, FAQQuestionUpdate, FAQQuestionResponse, FAQQuestionDetail,
    FAQQuestionPin, FAQAdminQuestionCreate,
    FAQAnswerCreate, FAQAnswerUpdate, FAQAnswerResponse,
)
from app.core.utils import escape_like
from app.services.audit_service import log_action

router = APIRouter(prefix="/faq", tags=["FAQ"])


# ── Helpers ───────────────────────────────────────────────────────


def _question_eager_options():
    return [selectinload(FAQQuestion.creator), selectinload(FAQQuestion.answers)]


def _question_to_response(q: FAQQuestion) -> dict:
    """Convert a FAQQuestion ORM object to a response dict."""
    all_answers = q.answers or []
    approved = [a for a in all_answers if a.status == FAQAnswerStatus.APPROVED.value]
    return {
        "id": q.id,
        "title": q.title,
        "description": q.description,
        "category": q.category,
        "status": q.status,
        "error_code": q.error_code,
        "created_by_user_id": q.created_by_user_id,
        "is_pinned": q.is_pinned,
        "view_count": q.view_count,
        "creator_name": q.creator.full_name if q.creator else "Unknown",
        "answer_count": len(all_answers),
        "approved_answer_count": len(approved),
        "created_at": q.created_at,
        "updated_at": q.updated_at,
        "archived_at": q.archived_at,
    }


def _answer_to_response(a: FAQAnswer) -> dict:
    """Convert a FAQAnswer ORM object to a response dict."""
    return {
        "id": a.id,
        "question_id": a.question_id,
        "content": a.content,
        "created_by_user_id": a.created_by_user_id,
        "status": a.status,
        "reviewed_by_user_id": a.reviewed_by_user_id,
        "reviewed_at": a.reviewed_at,
        "is_official": a.is_official,
        "creator_name": a.creator.full_name if a.creator else "Unknown",
        "reviewer_name": a.reviewer.full_name if a.reviewer else None,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def _notify_admins(db: Session, title: str, content: str, link: str) -> None:
    """Send a SYSTEM notification to all admin users."""
    admins = db.query(User).filter(
        or_(User.role == UserRole.ADMIN, User.roles.contains("admin"))
    ).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            type=NotificationType.SYSTEM,
            title=title,
            content=content,
            link=link,
        ))


def _notify_user(db: Session, user_id: int, title: str, content: str, link: str) -> None:
    """Send a SYSTEM notification to a specific user."""
    db.add(Notification(
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title=title,
        content=content,
        link=link,
    ))


# ── Public Endpoints ──────────────────────────────────────────────


@router.get("/questions", response_model=list[FAQQuestionResponse])
def list_questions(
    category: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    pinned_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List FAQ questions with optional filters. Excludes archived."""
    query = db.query(FAQQuestion).options(*_question_eager_options()).filter(
        FAQQuestion.archived_at.is_(None),
    )

    if category:
        query = query.filter(FAQQuestion.category == category.strip().lower())
    if status:
        query = query.filter(FAQQuestion.status == status.strip().lower())
    if pinned_only:
        query = query.filter(FAQQuestion.is_pinned == True)  # noqa: E712
    if search:
        term = f"%{escape_like(search.strip())}%"
        query = query.filter(
            or_(
                FAQQuestion.title.ilike(term),
                FAQQuestion.description.ilike(term),
            )
        )

    questions = query.order_by(
        FAQQuestion.is_pinned.desc(),
        FAQQuestion.created_at.desc(),
    ).offset(skip).limit(limit).all()

    return [_question_to_response(q) for q in questions]


@router.get("/by-error-code/{code}")
def get_by_error_code(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Look up a FAQ question by its error_code mapping."""
    question = db.query(FAQQuestion).filter(
        FAQQuestion.error_code == code,
        FAQQuestion.archived_at.is_(None),
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="No FAQ entry for this error code")
    return {"id": question.id, "title": question.title, "url": f"/faq/{question.id}"}


@router.get("/questions/{question_id}", response_model=FAQQuestionDetail)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get question detail with answers. Non-admin sees only approved answers."""
    question = db.query(FAQQuestion).options(
        selectinload(FAQQuestion.creator),
        selectinload(FAQQuestion.answers).selectinload(FAQAnswer.creator),
        selectinload(FAQQuestion.answers).selectinload(FAQAnswer.reviewer),
    ).filter(
        FAQQuestion.id == question_id,
        FAQQuestion.archived_at.is_(None),
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Increment view count
    question.view_count = (question.view_count or 0) + 1
    db.commit()

    # Filter answers based on role
    is_admin = current_user.has_role(UserRole.ADMIN) if hasattr(current_user, "has_role") else current_user.role == UserRole.ADMIN
    all_answers = question.answers or []
    if is_admin:
        visible_answers = all_answers
    else:
        visible_answers = [a for a in all_answers if a.status == FAQAnswerStatus.APPROVED.value]

    # Sort: official first, then by created_at
    visible_answers.sort(key=lambda a: (not a.is_official, a.created_at))

    resp = _question_to_response(question)
    resp["answers"] = [_answer_to_response(a) for a in visible_answers]
    return resp


@router.post("/questions", response_model=FAQQuestionResponse, status_code=201)
def create_question(
    data: FAQQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new FAQ question."""
    question = FAQQuestion(
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        category=data.category,
        created_by_user_id=current_user.id,
    )
    db.add(question)
    db.flush()

    log_action(db, user_id=current_user.id, action="create", resource_type="faq_question",
               resource_id=question.id, details={"title": question.title, "category": question.category})
    db.commit()
    db.refresh(question)
    return _question_to_response(question)


@router.patch("/questions/{question_id}", response_model=FAQQuestionResponse)
def update_question(
    question_id: int,
    data: FAQQuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a question. Creator or admin can edit."""
    question = db.query(FAQQuestion).options(*_question_eager_options()).filter(
        FAQQuestion.id == question_id,
        FAQQuestion.archived_at.is_(None),
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_admin = current_user.has_role(UserRole.ADMIN) if hasattr(current_user, "has_role") else current_user.role == UserRole.ADMIN
    if question.created_by_user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this question")

    if data.title is not None:
        question.title = data.title.strip()
    if data.description is not None:
        question.description = data.description.strip()
    if data.category is not None:
        question.category = data.category
    if data.status is not None and is_admin:
        question.status = data.status.strip().lower()

    log_action(db, user_id=current_user.id, action="update", resource_type="faq_question",
               resource_id=question.id, details={"title": question.title})
    db.commit()
    db.refresh(question)
    return _question_to_response(question)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a question. Creator or admin can delete."""
    question = db.query(FAQQuestion).filter(
        FAQQuestion.id == question_id,
        FAQQuestion.archived_at.is_(None),
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_admin = current_user.has_role(UserRole.ADMIN) if hasattr(current_user, "has_role") else current_user.role == UserRole.ADMIN
    if question.created_by_user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this question")

    question.archived_at = datetime.now(timezone.utc)
    log_action(db, user_id=current_user.id, action="delete", resource_type="faq_question",
               resource_id=question.id, details={"title": question.title})
    db.commit()


@router.post("/questions/{question_id}/answers", response_model=FAQAnswerResponse, status_code=201)
def submit_answer(
    question_id: int,
    data: FAQAnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an answer. Auto-approved for admins, pending for others."""
    question = db.query(FAQQuestion).filter(
        FAQQuestion.id == question_id,
        FAQQuestion.archived_at.is_(None),
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_admin = current_user.has_role(UserRole.ADMIN) if hasattr(current_user, "has_role") else current_user.role == UserRole.ADMIN

    answer = FAQAnswer(
        question_id=question_id,
        content=data.content,
        created_by_user_id=current_user.id,
        status=FAQAnswerStatus.APPROVED.value if is_admin else FAQAnswerStatus.PENDING.value,
    )

    if is_admin:
        answer.reviewed_by_user_id = current_user.id
        answer.reviewed_at = datetime.now(timezone.utc)
        # Update question status to answered if first approved answer
        if question.status == FAQQuestionStatus.OPEN.value:
            question.status = FAQQuestionStatus.ANSWERED.value

    db.add(answer)
    db.flush()

    # Notify admins about new pending answer (skip if admin submitted)
    if not is_admin:
        _notify_admins(
            db,
            title="New FAQ answer pending review",
            content=f"A new answer was submitted for: {question.title}",
            link=f"/admin/faq",
        )

    log_action(db, user_id=current_user.id, action="create", resource_type="faq_answer",
               resource_id=answer.id, details={"question_id": question_id})
    db.commit()
    db.refresh(answer)
    return _answer_to_response(answer)


@router.patch("/answers/{answer_id}", response_model=FAQAnswerResponse)
def update_answer(
    answer_id: int,
    data: FAQAnswerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit own answer (only while pending)."""
    answer = db.query(FAQAnswer).options(
        selectinload(FAQAnswer.creator),
        selectinload(FAQAnswer.reviewer),
    ).filter(FAQAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    if answer.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this answer")

    if answer.status != FAQAnswerStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Can only edit pending answers")

    if data.content is not None:
        answer.content = data.content

    db.commit()
    db.refresh(answer)
    return _answer_to_response(answer)


# ── Admin Endpoints ───────────────────────────────────────────────


@router.get("/admin/pending", response_model=list[FAQAnswerResponse])
def list_pending_answers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List answers pending approval (admin only)."""
    answers = db.query(FAQAnswer).options(
        selectinload(FAQAnswer.creator),
        selectinload(FAQAnswer.reviewer),
    ).filter(
        FAQAnswer.status == FAQAnswerStatus.PENDING.value,
    ).order_by(
        FAQAnswer.created_at.asc(),
    ).offset(skip).limit(limit).all()

    return [_answer_to_response(a) for a in answers]


@router.patch("/admin/answers/{answer_id}/approve", response_model=FAQAnswerResponse)
def approve_answer(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Approve a pending answer."""
    answer = db.query(FAQAnswer).options(
        selectinload(FAQAnswer.creator),
        selectinload(FAQAnswer.question),
    ).filter(FAQAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.status != FAQAnswerStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Answer is not pending")

    answer.status = FAQAnswerStatus.APPROVED.value
    answer.reviewed_by_user_id = current_user.id
    answer.reviewed_at = datetime.now(timezone.utc)

    # Update question status to answered if first approved answer
    question = answer.question
    if question and question.status == FAQQuestionStatus.OPEN.value:
        question.status = FAQQuestionStatus.ANSWERED.value

    # Notify the answer author
    _notify_user(
        db, answer.created_by_user_id,
        title="Your FAQ answer was approved",
        content=f"Your answer to \"{question.title}\" has been approved.",
        link=f"/faq/{question.id}",
    )

    log_action(db, user_id=current_user.id, action="approve", resource_type="faq_answer",
               resource_id=answer.id, details={"question_id": answer.question_id})
    db.commit()
    db.refresh(answer)
    return _answer_to_response(answer)


@router.patch("/admin/answers/{answer_id}/reject", response_model=FAQAnswerResponse)
def reject_answer(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Reject a pending answer."""
    answer = db.query(FAQAnswer).options(
        selectinload(FAQAnswer.creator),
        selectinload(FAQAnswer.question),
    ).filter(FAQAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.status != FAQAnswerStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Answer is not pending")

    answer.status = FAQAnswerStatus.REJECTED.value
    answer.reviewed_by_user_id = current_user.id
    answer.reviewed_at = datetime.now(timezone.utc)

    question = answer.question
    _notify_user(
        db, answer.created_by_user_id,
        title="Your FAQ answer was not approved",
        content=f"Your answer to \"{question.title}\" was not approved.",
        link=f"/faq/{question.id}",
    )

    log_action(db, user_id=current_user.id, action="reject", resource_type="faq_answer",
               resource_id=answer.id, details={"question_id": answer.question_id})
    db.commit()
    db.refresh(answer)
    return _answer_to_response(answer)


@router.patch("/admin/questions/{question_id}/pin", response_model=FAQQuestionResponse)
def toggle_pin(
    question_id: int,
    data: FAQQuestionPin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Pin or unpin a question."""
    question = db.query(FAQQuestion).options(*_question_eager_options()).filter(
        FAQQuestion.id == question_id,
        FAQQuestion.archived_at.is_(None),
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.is_pinned = data.is_pinned
    log_action(db, user_id=current_user.id, action="pin" if data.is_pinned else "unpin",
               resource_type="faq_question", resource_id=question.id)
    db.commit()
    db.refresh(question)
    return _question_to_response(question)


@router.patch("/admin/answers/{answer_id}/mark-official", response_model=FAQAnswerResponse)
def mark_official(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Toggle the official/best answer flag. Unmarks other official answers on the same question."""
    answer = db.query(FAQAnswer).options(
        selectinload(FAQAnswer.creator),
        selectinload(FAQAnswer.reviewer),
    ).filter(FAQAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.status != FAQAnswerStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="Only approved answers can be marked official")

    if answer.is_official:
        # Toggle off
        answer.is_official = False
    else:
        # Unmark existing official answers for this question
        db.query(FAQAnswer).filter(
            FAQAnswer.question_id == answer.question_id,
            FAQAnswer.is_official == True,  # noqa: E712
        ).update({"is_official": False})
        answer.is_official = True

    log_action(db, user_id=current_user.id, action="mark_official", resource_type="faq_answer",
               resource_id=answer.id, details={"is_official": answer.is_official})
    db.commit()
    db.refresh(answer)
    return _answer_to_response(answer)


@router.delete("/admin/answers/{answer_id}", status_code=204)
def admin_delete_answer(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Permanently delete an answer (admin only)."""
    answer = db.query(FAQAnswer).filter(FAQAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    log_action(db, user_id=current_user.id, action="delete", resource_type="faq_answer",
               resource_id=answer.id, details={"question_id": answer.question_id})
    db.delete(answer)
    db.commit()


@router.post("/admin/questions", response_model=FAQQuestionDetail, status_code=201)
def create_official_faq(
    data: FAQAdminQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create an official FAQ entry (question + auto-approved answer in one shot)."""
    question = FAQQuestion(
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        category=data.category,
        status=FAQQuestionStatus.ANSWERED.value,
        created_by_user_id=current_user.id,
    )
    db.add(question)
    db.flush()

    answer = FAQAnswer(
        question_id=question.id,
        content=data.answer_content.strip(),
        created_by_user_id=current_user.id,
        status=FAQAnswerStatus.APPROVED.value,
        is_official=data.is_official,
        reviewed_by_user_id=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(answer)
    db.flush()

    log_action(db, user_id=current_user.id, action="create", resource_type="faq_official",
               resource_id=question.id, details={"title": question.title})
    db.commit()
    db.refresh(question)
    db.refresh(answer)

    resp = _question_to_response(question)
    resp["answers"] = [_answer_to_response(answer)]
    return resp
