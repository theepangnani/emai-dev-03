GREETING_KEYWORDS = {"hi", "hello", "hey", "help", "menu", "start", "options"}

SEARCH_KEYWORDS = [
    "find", "search", "show me", "list", "where is", "where are",
    "my courses", "my tasks", "my study", "my notes", "my materials",
    "course", "task", "study guide", "quiz", "flashcard", "material",
    "note", "assignment",
]

HELP_KEYWORDS = [
    "how", "why", "what is", "explain", "help me", "tutorial", "guide",
    "can i", "how do i", "what does", "how to",
]

ACTION_KEYWORDS = ["upload", "create", "add", "new course", "new task", "generate"]


def classify_intent(message: str, openai_api_key: str | None = None) -> str:
    """
    Returns 'search' | 'action' | 'help'.

    Uses keyword matching first (fast, $0). Falls back to embedding similarity
    for ambiguous messages when openai_api_key is provided.
    """
    msg = message.lower().strip()

    # Greetings and menu commands always go to help (show suggestion chips)
    if msg in GREETING_KEYWORDS:
        return "help"

    # Check action first (most specific)
    if any(kw in msg for kw in ACTION_KEYWORDS):
        if any(hkw in msg for hkw in ["how to", "how do i", "tutorial"]):
            return "help"
        return "action"

    # Search intent
    if any(kw in msg for kw in SEARCH_KEYWORDS):
        if any(hkw in msg for hkw in ["how to", "how do i", "tutorial", "explain"]):
            return "help"
        return "search"

    # Help keywords — explicit help request, skip embedding
    if any(kw in msg for kw in HELP_KEYWORDS):
        return "help"

    # Embedding fallback for ambiguous messages (e.g. bare names, natural phrasing)
    if openai_api_key:
        from app.services.intent_embedding_service import intent_embedding_service
        result = intent_embedding_service.classify(message, openai_api_key)
        if result is not None:
            return result

    # Single bare-word queries with no keywords are almost always search intent (e.g. a name)
    words = msg.split()
    if len(words) == 1 and not any(hkw in msg for hkw in HELP_KEYWORDS):
        return "search"

    # Final default
    return "help"
