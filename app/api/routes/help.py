import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse as _StreamingResponse
from sqlalchemy import and_, or_
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
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)

    words = q.strip().split()
    word_filters = []
    for word in words:
        term = f"%{escape_like(word)}%"
        word_filters.append(or_(HelpArticle.title.ilike(term), HelpArticle.content.ilike(term)))

    results = db.query(HelpArticle).filter(
        and_(*word_filters),
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

    from app.core.config import settings
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    intent = classify_intent(request.message, openai_api_key=settings.openai_api_key)

    if intent in ("search", "action"):
        results = search_service.search(
            query=request.message,
            user_id=current_user.id,
            user_role=user_role,
            db=db,
        )
        if results:
            reply = f"Here's what I found for **\"{request.message}\"**:"
            return_intent = intent
        else:
            reply = f"No results found for **\"{request.message}\"**. Try asking me a question about ClassBridge instead."
            return_intent = "help"

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
            intent=return_intent,
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


@router.post("/chat/stream")
async def help_chat_stream(
    request: HelpChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming version of /chat — returns SSE token stream for help responses."""
    from app.services.intent_classifier import classify_intent
    from app.services.search_service import search_service
    from app.services.help_chat_service import help_chat_service, SYSTEM_PROMPT
    from app.core.config import settings
    import anthropic

    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    intent = classify_intent(request.message, openai_api_key=settings.openai_api_key)

    async def event_stream():
        # Search/action: emit single event with full results
        if intent in ("search", "action"):
            results = search_service.search(
                query=request.message,
                user_id=current_user.id,
                user_role=user_role,
                db=db,
            )
            if results:
                reply = f"Here's what I found for **\"{request.message}\"**:"
                return_intent = intent
            else:
                reply = f"No results found for **\"{request.message}\"**. Try asking me a question about ClassBridge instead."
                return_intent = "help"

            payload = {
                "type": "search",
                "reply": reply,
                "intent": return_intent,
                "search_results": [
                    {
                        "entity_type": r.entity_type,
                        "id": r.id,
                        "title": r.title,
                        "description": r.description,
                        "actions": r.actions,
                    }
                    for r in results
                ],
            }
            yield f"data: {json.dumps(payload)}\n\n"
            return

        # Help flow: stream tokens from Claude
        try:
            from app.services.help_embedding_service import help_embedding_service
            chunks = await help_embedding_service.search(
                query=request.message,
                top_k=5,
                role_filter=user_role,
            )
            context_text = help_chat_service._format_chunks_for_prompt(chunks)
            system_prompt = SYSTEM_PROMPT.format(
                user_role=user_role,
                current_page=request.page_context or "unknown",
                retrieved_chunks=context_text,
            )

            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation
            ]
            messages = []
            for msg in conversation_history[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"][:500]})
            messages.append({"role": "user", "content": request.message})

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.strip())
            async with client.messages.stream(
                model=settings.claude_model,
                system=system_prompt,
                messages=messages,
                max_tokens=800,
                temperature=0.3,
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"

            # Done event: send sources and videos
            sources = [chunk.source_id for chunk in chunks if chunk.score > 0.3]
            videos = help_chat_service._extract_videos(chunks)
            done_payload = {
                "type": "done",
                "sources": sources,
                "videos": [
                    {"title": v.title, "url": v.url, "provider": v.provider}
                    for v in videos
                ],
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Streaming chat failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': 'Something went wrong. Please try again.'})}\n\n"

    return _StreamingResponse(event_stream(), media_type="text/event-stream")
