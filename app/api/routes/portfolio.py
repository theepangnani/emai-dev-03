"""Portfolio API routes — students curate their best work; parents can view."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.portfolio import StudentPortfolio
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioItemCreate,
    PortfolioItemResponse,
    PortfolioItemUpdate,
    PortfolioResponse,
    PortfolioUpdate,
    ReorderRequest,
)
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
_svc = PortfolioService()


# ---------------------------------------------------------------------------
# Helper: verify parent owns a student
# ---------------------------------------------------------------------------

def _verify_parent_child(parent_user: User, student_user_id: int, db: Session) -> None:
    """Raise 403 if *parent_user* does not have the student with *student_user_id* as a linked child."""
    # Find the Student record whose user_id matches student_user_id
    student = db.query(Student).filter(Student.user_id == student_user_id).first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    link = db.execute(
        parent_students.select().where(
            parent_students.c.parent_id == parent_user.id,
            parent_students.c.student_id == student.id,
        )
    ).first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your child's portfolio")


# ---------------------------------------------------------------------------
# Portfolio routes
# ---------------------------------------------------------------------------

@router.get("/me", response_model=PortfolioResponse)
def get_my_portfolio(
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: get or auto-create own portfolio."""
    portfolio = _svc.get_portfolio(student_id=current_user.id, db=db)
    return portfolio


@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    data: PortfolioCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: explicitly create a portfolio."""
    portfolio = _svc.create_portfolio(student_id=current_user.id, data=data, db=db)
    return portfolio


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
def update_portfolio(
    portfolio_id: int,
    data: PortfolioUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: update portfolio metadata (title, description, visibility)."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")

    updated = _svc.update_portfolio(portfolio_id=portfolio_id, data=data, db=db)
    return updated


# ---------------------------------------------------------------------------
# Item routes
# ---------------------------------------------------------------------------

@router.post("/{portfolio_id}/items", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    portfolio_id: int,
    data: PortfolioItemCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: add an item to their portfolio."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")

    item = _svc.add_item(portfolio_id=portfolio_id, item_data=data, db=db)
    return item


@router.patch("/{portfolio_id}/items/{item_id}", response_model=PortfolioItemResponse)
def update_item(
    portfolio_id: int,
    item_id: int,
    data: PortfolioItemUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: update a portfolio item (reflection, tags, order)."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")

    item = _svc.update_item(item_id=item_id, data=data, db=db)
    if item is None or item.portfolio_id != portfolio_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.delete("/{portfolio_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    portfolio_id: int,
    item_id: int,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: remove an item from their portfolio."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")

    deleted = _svc.remove_item(item_id=item_id, db=db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")


@router.post("/{portfolio_id}/reorder", response_model=list[PortfolioItemResponse])
def reorder_items(
    portfolio_id: int,
    data: ReorderRequest,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student: reorder portfolio items by providing an ordered list of item IDs."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")

    items = _svc.reorder_items(portfolio_id=portfolio_id, item_ids=data.item_ids, db=db)
    return items


# ---------------------------------------------------------------------------
# AI summary + export (student or parent)
# ---------------------------------------------------------------------------

@router.get("/{portfolio_id}/summary")
async def get_portfolio_summary(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Student or parent: get an AI-generated portfolio summary."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    if current_user.has_role(UserRole.STUDENT):
        if portfolio.student_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")
    elif current_user.has_role(UserRole.PARENT):
        _verify_parent_child(current_user, portfolio.student_id, db)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    summary = await _svc.generate_summary(portfolio_id=portfolio_id, db=db)
    return {"summary": summary}


@router.get("/{portfolio_id}/export")
def export_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Student or parent: export the full portfolio as JSON."""
    portfolio = _svc.get_portfolio_by_id(portfolio_id, db)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    if current_user.has_role(UserRole.STUDENT):
        if portfolio.student_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")
    elif current_user.has_role(UserRole.PARENT):
        _verify_parent_child(current_user, portfolio.student_id, db)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return _svc.export_portfolio(portfolio_id=portfolio_id, db=db)


# ---------------------------------------------------------------------------
# Parent: view child's portfolio
# ---------------------------------------------------------------------------

@router.get("/student/{student_id}", response_model=PortfolioResponse)
def get_child_portfolio(
    student_id: int,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Parent: view a linked child's portfolio."""
    _verify_parent_child(current_user, student_id, db)
    portfolio = _svc.get_portfolio(student_id=student_id, db=db)
    return portfolio
