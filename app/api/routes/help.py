from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.help import HelpChatRequest, HelpChatResponse, VideoResponse

router = APIRouter(prefix="/help", tags=["help"])


@router.post("/chat", response_model=HelpChatResponse)
async def help_chat(
    request: HelpChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a message to the ClassBridge Help Assistant."""
    from app.services.help_chat_service import help_chat_service

    # Get user role
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)

    # Build conversation history
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.conversation
    ]

    # Generate response
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
    )
