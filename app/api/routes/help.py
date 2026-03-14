from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like
from app.db.database import get_db
from app.models.help_article import HelpArticle
from app.models.user import User
from app.schemas.help import HelpArticleResponse, HelpChatRequest, HelpChatResponse, VideoResponse, SearchResultItem, SearchResultAction

router = APIRouter(prefix="/help", tags=["help"])


# -- Articles --


@router.get("/articles", response_model=list[HelpArticleResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_articles(
    request: Request,
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all help articles, optionally filtered by category."""
    query = db.query(HelpArticle)
    if category:
        query = query.filter(HelpArticle.category == category.strip())

    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    query = query.filter(
        or_(HelpArticle.role.is_(None), HelpArticle.role == "", HelpArticle.role.contains(user_role))
    )

    return query.order_by(HelpArticle.display_order, HelpArticle.title).all()


@router.get("/articles/{slug}", response_model=HelpArticleResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_article(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single help article by slug."""
    article = db.query(HelpArticle).filter(HelpArticle.slug == slug).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/search", response_model=list[HelpArticleResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def search_articles(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search help articles by title and content."""
    term = f"%{escape_like(q.strip())}%"
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)

    results = db.query(HelpArticle).filter(
        or_(HelpArticle.title.ilike(term), HelpArticle.content.ilike(term)),
        or_(HelpArticle.role.is_(None), HelpArticle.role == "", HelpArticle.role.contains(user_role)),
    ).order_by(HelpArticle.display_order, HelpArticle.title).limit(20).all()

    return results


# -- Chatbot --


@router.post("/chat", response_model=HelpChatResponse)
async def help_chat(
    request: HelpChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to the ClassBridge Help Assistant."""
    from app.services.intent_classifier import classify_intent
    from app.services.search_service import search_service
    from app.services.help_chat_service import help_chat_service

    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    intent = classify_intent(request.message)

    if intent in ("search", "action"):
        results = search_service.search(
            query=request.message,
            user_id=current_user.id,
            user_role=user_role,
            db=db,
        )
        if results:
            reply = f"Here's what I found for **\"{request.message}\"**:"
        else:
            reply = f"No results found for **\"{request.message}\"**. Try a different search term or ask me a question about ClassBridge."

        return HelpChatResponse(
            reply=reply,
            sources=[],
            videos=[],
            search_results=[
                SearchResultItem(
                    entity_type=r.entity_type,
                    id=r.id,
                    title=r.title,
                    description=r.description,
                    actions=[SearchResultAction(label=a["label"], route=a["route"]) for a in r.actions],
                )
                for r in results
            ],
            intent=intent,
        )

    # Help flow (existing)
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.conversation
    ]

    result = await help_chat_service.generate_response(
        message=request.message,
        user_id=current_user.id,
        user_role=user_role,
        page_context=request.page_context,
        conversation_history=conversation_history,
    )

    return HelpChatResponse(
        reply=result.reply,
        sources=result.sources,
        videos=[
            VideoResponse(
                title=v.title,
                url=v.url,
                provider=v.provider,
            )
            for v in result.videos
        ],
        search_results=[],
        intent="help",
    )
