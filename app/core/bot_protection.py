import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def is_bot_submission(
    honeypot_value: str = "",
    started_at: Optional[float] = None,
    min_seconds: float = 3.0,
) -> bool:
    """Check if a form submission appears to be from a bot.

    Returns True if bot-like behavior is detected.
    """
    # Honeypot: bots fill hidden fields
    if honeypot_value:
        logger.info("Bot detected: honeypot field filled")
        return True

    # Timing: bots submit too fast
    if started_at is not None:
        elapsed = time.time() - started_at
        if elapsed < min_seconds:
            logger.info(f"Bot detected: completed in {elapsed:.1f}s (min: {min_seconds}s)")
            return True

    return False
