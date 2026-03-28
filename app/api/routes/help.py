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

    # --- §6.114: Study Q&A mode ---
    if request.study_guide_id:
        return await _handle_study_qa_non_streaming(request, db, current_user)

    from app.services.intent_classifier import classify_intent
    from app.services.search_service import search_service
    from app.services.help_chat_service import help_chat_service

    from app.core.config import settings
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    intent = classify_intent(request.message, openai_api_key=settings.openai_api_key)

    no_results_suggestion_chips = [
        "Getting started",
        "Study tools",
        "Google Classroom",
        "Account settings",
        "Upload materials",
    ]

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
            suggestion_chips=no_results_suggestion_chips if not results else [],
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

    # --- §6.114: Study Q&A mode ---
    if request.study_guide_id:
        return await _handle_study_qa_stream(request, db, current_user)

    from app.services.intent_classifier import classify_intent
    from app.services.search_service import search_service
    from app.services.help_chat_service import help_chat_service, SYSTEM_PROMPT
    from app.core.config import settings
    import anthropic

    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    intent = classify_intent(request.message, openai_api_key=settings.openai_api_key)

    no_results_suggestion_chips = [
        "Getting started",
        "Study tools",
        "Google Classroom",
        "Account settings",
        "Upload materials",
    ]

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
                "suggestion_chips": no_results_suggestion_chips if not results else [],
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


# ---------------------------------------------------------------------------
# §6.114 — Study Guide Contextual Q&A helpers
# ---------------------------------------------------------------------------

def _load_study_guide_for_qa(guide_id: int, user: User, db: Session):
    """Load a study guide and verify the user has access. Returns (guide, source_text)."""
    from app.models.study_guide import StudyGuide
    from app.models.course_content import CourseContent

    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Access check: owner, shared with user, or parent of owner
    has_access = (
        guide.user_id == user.id
        or guide.shared_with_user_id == user.id
    )
    if not has_access:
        # Check parent-of-owner (parent_students.student_id -> students.id,
        # so we must join through students to match on user_id)
        from app.models.student import Student, parent_students
        link = db.execute(
            parent_students.select().where(
                and_(
                    parent_students.c.parent_id == user.id,
                    parent_students.c.student_id.in_(
                        db.query(Student.id).filter(Student.user_id == guide.user_id)
                    ),
                )
            )
        ).first()
        if link:
            has_access = True

    # Fallback: course-based access (enrolled student, public course, teacher, etc.)
    if not has_access and guide.course_content_id:
        from app.api.deps import can_access_material
        cc = db.query(CourseContent).filter(CourseContent.id == guide.course_content_id).first()
        if cc and can_access_material(db, user, cc):
            has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied to this study guide")

    # Load source document text if available
    source_text = None
    if guide.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == guide.course_content_id).first()
        if cc and cc.text_content:
            source_text = cc.text_content

    return guide, source_text


async def _handle_study_qa_stream(request: HelpChatRequest, db: Session, user: User):
    """SSE streaming study Q&A — §6.114."""
    from decimal import Decimal
    from app.services.study_qa_service import study_qa_service
    from app.services.ai_usage import check_ai_usage, increment_ai_usage

    guide, source_text = _load_study_guide_for_qa(request.study_guide_id, user, db)

    # Credit check
    check_ai_usage(user, db)

    async def event_stream():
        last_done = None
        async for event in study_qa_service.stream_answer(
            guide_title=guide.title,
            guide_content=guide.content or "",
            source_content=source_text,
            message=request.message,
            user_id=user.id,
            conversation_history=[
                {"role": m.role, "content": m.content}
                for m in request.conversation
            ],
        ):
            if event.get("type") == "done":
                last_done = event
            yield f"data: {json.dumps(event)}\n\n"

        # Debit credits after successful completion
        if last_done:
            try:
                increment_ai_usage(
                    user, db,
                    generation_type="study_qa",
                    course_material_id=guide.course_content_id,
                    prompt_tokens=last_done.get("input_tokens"),
                    completion_tokens=last_done.get("output_tokens"),
                    total_tokens=(last_done.get("input_tokens", 0) or 0) + (last_done.get("output_tokens", 0) or 0),
                    estimated_cost_usd=last_done.get("estimated_cost_usd"),
                    model_name="claude-haiku-4-5-20251001",
                    wallet_debit_amount=Decimal("0.25"),
                )
            except Exception:
                import logging
                logging.getLogger(__name__).warning("Failed to debit study Q&A credits for user_id=%s", user.id, exc_info=True)

    return _StreamingResponse(event_stream(), media_type="text/event-stream")


async def _handle_study_qa_non_streaming(request: HelpChatRequest, db: Session, user: User) -> HelpChatResponse:
    """Non-streaming study Q&A fallback — §6.114."""
    from decimal import Decimal
    from app.services.study_qa_service import study_qa_service
    from app.services.ai_usage import check_ai_usage, increment_ai_usage

    guide, source_text = _load_study_guide_for_qa(request.study_guide_id, user, db)
    check_ai_usage(user, db)

    reply_parts = []
    last_done = None

    async for event in study_qa_service.stream_answer(
        guide_title=guide.title,
        guide_content=guide.content or "",
        source_content=source_text,
        message=request.message,
        user_id=user.id,
        conversation_history=[
            {"role": m.role, "content": m.content}
            for m in request.conversation
        ],
    ):
        if event.get("type") == "token":
            reply_parts.append(event["text"])
        elif event.get("type") == "done":
            last_done = event
        elif event.get("type") == "error":
            raise HTTPException(status_code=500, detail=event.get("text", "Study Q&A failed"))

    # Debit credits
    if last_done:
        try:
            increment_ai_usage(
                user, db,
                generation_type="study_qa",
                course_material_id=guide.course_content_id,
                prompt_tokens=last_done.get("input_tokens"),
                completion_tokens=last_done.get("output_tokens"),
                total_tokens=(last_done.get("input_tokens", 0) or 0) + (last_done.get("output_tokens", 0) or 0),
                estimated_cost_usd=last_done.get("estimated_cost_usd"),
                model_name="claude-haiku-4-5-20251001",
                wallet_debit_amount=Decimal("0.25"),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to debit study Q&A credits for user_id=%s", user.id, exc_info=True)

    return HelpChatResponse(
        reply="".join(reply_parts),
        sources=[],
        videos=[],
        mode="study_qa",
        credits_used=float(last_done.get("credits_used", 0.25)) if last_done else 0.25,
        input_tokens=last_done.get("input_tokens") if last_done else None,
        output_tokens=last_done.get("output_tokens") if last_done else None,
        estimated_cost_usd=last_done.get("estimated_cost_usd") if last_done else None,
    )
