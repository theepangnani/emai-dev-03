"""Service layer for the student portfolio feature."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.portfolio import PortfolioItem, PortfolioItemType, StudentPortfolio
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioItemCreate,
    PortfolioItemUpdate,
    PortfolioUpdate,
)

logger = logging.getLogger(__name__)


class PortfolioService:
    """Business logic for student portfolios."""

    # ------------------------------------------------------------------
    # Portfolio CRUD
    # ------------------------------------------------------------------

    def create_portfolio(self, student_id: int, data: PortfolioCreate, db: Session) -> StudentPortfolio:
        """Create a new portfolio for a student."""
        portfolio = StudentPortfolio(
            student_id=student_id,
            title=data.title,
            description=data.description,
            is_public=data.is_public,
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        logger.info("Created portfolio id=%d for student_id=%d", portfolio.id, student_id)
        return portfolio

    def get_portfolio(self, student_id: int, db: Session) -> StudentPortfolio:
        """Return the student's portfolio (creates a default one if none exists)."""
        portfolio = (
            db.query(StudentPortfolio)
            .filter(StudentPortfolio.student_id == student_id)
            .first()
        )
        if portfolio is None:
            portfolio = self.create_portfolio(
                student_id,
                PortfolioCreate(title="My Portfolio"),
                db,
            )
        return portfolio

    def get_portfolio_by_id(self, portfolio_id: int, db: Session) -> Optional[StudentPortfolio]:
        """Return a specific portfolio by its primary key."""
        return db.query(StudentPortfolio).filter(StudentPortfolio.id == portfolio_id).first()

    def update_portfolio(
        self, portfolio_id: int, data: PortfolioUpdate, db: Session
    ) -> Optional[StudentPortfolio]:
        """Update portfolio metadata."""
        portfolio = self.get_portfolio_by_id(portfolio_id, db)
        if portfolio is None:
            return None
        if data.title is not None:
            portfolio.title = data.title
        if data.description is not None:
            portfolio.description = data.description
        if data.is_public is not None:
            portfolio.is_public = data.is_public
        db.commit()
        db.refresh(portfolio)
        return portfolio

    # ------------------------------------------------------------------
    # Portfolio Item CRUD
    # ------------------------------------------------------------------

    def add_item(self, portfolio_id: int, item_data: PortfolioItemCreate, db: Session) -> PortfolioItem:
        """Add an item to a portfolio."""
        tags_json = json.dumps(item_data.tags or [])
        item = PortfolioItem(
            portfolio_id=portfolio_id,
            item_type=item_data.item_type,
            item_id=item_data.item_id,
            title=item_data.title,
            description=item_data.description,
            tags=tags_json,
            display_order=item_data.display_order,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        logger.info(
            "Added portfolio item id=%d (type=%s) to portfolio_id=%d",
            item.id,
            item_data.item_type,
            portfolio_id,
        )
        return item

    def update_item(
        self, item_id: int, data: PortfolioItemUpdate, db: Session
    ) -> Optional[PortfolioItem]:
        """Update a portfolio item."""
        item = db.query(PortfolioItem).filter(PortfolioItem.id == item_id).first()
        if item is None:
            return None
        if data.title is not None:
            item.title = data.title
        if data.description is not None:
            item.description = data.description
        if data.tags is not None:
            item.tags = json.dumps(data.tags)
        if data.display_order is not None:
            item.display_order = data.display_order
        db.commit()
        db.refresh(item)
        return item

    def remove_item(self, item_id: int, db: Session) -> bool:
        """Delete a portfolio item. Returns True if deleted, False if not found."""
        item = db.query(PortfolioItem).filter(PortfolioItem.id == item_id).first()
        if item is None:
            return False
        db.delete(item)
        db.commit()
        logger.info("Deleted portfolio item id=%d", item_id)
        return True

    def reorder_items(
        self, portfolio_id: int, item_ids: list[int], db: Session
    ) -> list[PortfolioItem]:
        """Update display_order of items according to the provided ordering."""
        items = (
            db.query(PortfolioItem)
            .filter(
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.id.in_(item_ids),
            )
            .all()
        )
        item_map = {item.id: item for item in items}
        for order, item_id in enumerate(item_ids):
            if item_id in item_map:
                item_map[item_id].display_order = order
        db.commit()
        # Return items in new order
        for item in item_map.values():
            db.refresh(item)
        return sorted(item_map.values(), key=lambda i: i.display_order)

    # ------------------------------------------------------------------
    # AI summary & export
    # ------------------------------------------------------------------

    async def generate_summary(self, portfolio_id: int, db: Session) -> str:
        """Generate an AI summary of the portfolio using the configured AI service."""
        from app.services.ai_service import generate_content

        portfolio = self.get_portfolio_by_id(portfolio_id, db)
        if portfolio is None:
            return "Portfolio not found."

        items = portfolio.items
        n = len(items)

        if n == 0:
            return (
                "This portfolio is currently empty. Add study guides, quiz results, "
                "notes, and other achievements to generate a meaningful summary."
            )

        # Build a concise description of each item for the prompt
        item_lines = []
        type_counts: dict[str, int] = {}
        for item in items:
            type_label = item.item_type.value.replace("_", " ").title()
            type_counts[type_label] = type_counts.get(type_label, 0) + 1
            tags_list = []
            if item.tags:
                try:
                    tags_list = json.loads(item.tags)
                except (json.JSONDecodeError, ValueError):
                    tags_list = []
            tag_str = f" [Tags: {', '.join(tags_list)}]" if tags_list else ""
            reflection = f" — Reflection: {item.description}" if item.description else ""
            item_lines.append(f"- {type_label}: {item.title}{tag_str}{reflection}")

        subjects_summary = ", ".join(
            f"{count} {label}" for label, count in type_counts.items()
        )
        items_text = "\n".join(item_lines)

        prompt = (
            f"Based on this student's portfolio of {n} items covering {subjects_summary}, "
            f"here is a professional summary of their academic work and achievements:\n\n"
            f"Portfolio title: {portfolio.title}\n"
            f"Portfolio description: {portfolio.description or 'N/A'}\n\n"
            f"Items:\n{items_text}\n\n"
            f"Please write a 3-5 sentence professional summary highlighting the student's "
            f"breadth of work, key strengths demonstrated, and overall academic engagement. "
            f"Write in third person (e.g. 'This student...'). Be encouraging and professional."
        )

        system_prompt = (
            "You are an academic counsellor writing professional portfolio summaries "
            "for students. Summarize the student's portfolio in a positive, professional tone "
            "suitable for sharing with parents, teachers, or future educators."
        )

        try:
            summary = await generate_content(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=400,
                temperature=0.6,
            )
            return summary
        except Exception as exc:
            logger.error("AI summary generation failed for portfolio_id=%d: %s", portfolio_id, exc)
            return (
                f"This student has curated a portfolio of {n} items including {subjects_summary}. "
                f"The portfolio titled '{portfolio.title}' reflects their academic journey and engagement "
                f"across multiple subjects and activity types."
            )

    def export_portfolio(self, portfolio_id: int, db: Session) -> dict:
        """Return a structured JSON-serialisable export of the portfolio."""
        portfolio = self.get_portfolio_by_id(portfolio_id, db)
        if portfolio is None:
            return {}

        items_data = []
        for item in portfolio.items:
            tags = []
            if item.tags:
                try:
                    tags = json.loads(item.tags)
                except (json.JSONDecodeError, ValueError):
                    tags = []
            items_data.append(
                {
                    "id": item.id,
                    "item_type": item.item_type.value,
                    "item_id": item.item_id,
                    "title": item.title,
                    "description": item.description,
                    "tags": tags,
                    "display_order": item.display_order,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
            )

        return {
            "portfolio": {
                "id": portfolio.id,
                "student_id": portfolio.student_id,
                "title": portfolio.title,
                "description": portfolio.description,
                "is_public": portfolio.is_public,
                "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None,
                "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None,
            },
            "items": items_data,
            "item_count": len(items_data),
        }
