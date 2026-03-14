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


def classify_intent(message: str) -> str:
    """Returns 'search' | 'action' | 'help'"""
    msg = message.lower().strip()

    # Check action first (most specific)
    if any(kw in msg for kw in ACTION_KEYWORDS):
        # But "how to create" is help, not action
        if any(hkw in msg for hkw in ["how to", "how do i", "tutorial"]):
            return "help"
        return "action"

    # Search intent
    if any(kw in msg for kw in SEARCH_KEYWORDS):
        # "how to find" is help
        if any(hkw in msg for hkw in ["how to", "how do i", "tutorial", "explain"]):
            return "help"
        return "search"

    # Default to help
    return "help"
