import logging
from typing import Optional

logger = logging.getLogger(__name__)


def is_bot_submission(
    honeypot_value: str = "",
    elapsed_seconds: Optional[float] = None,
    min_seconds: float = 3.0,
) -> bool:
    """Check if a form submission appears to be from a bot.

    Returns True if bot-like behavior is detected.
    """
    # Honeypot: bots fill hidden fields
    if honeypot_value:
        logger.info("Bot detected: honeypot field filled")
        return True

    # Timing: client reports elapsed seconds since form load
    if elapsed_seconds is not None:
        if elapsed_seconds < 0 or elapsed_seconds > 86400:
            logger.info(f"Bot detected: suspicious elapsed time {elapsed_seconds:.1f}s")
            return True
        if elapsed_seconds < min_seconds:
            logger.info(f"Bot detected: form completed in {elapsed_seconds:.1f}s (min: {min_seconds}s)")
            return True

    return False
