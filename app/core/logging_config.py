"""
Logging configuration for EMAI application.
Implements rotating file logs with 10 MB max size.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Log directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log file settings
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5  # Keep 5 backup files

# Log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_file_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    """Create a rotating file handler."""
    log_file = LOG_DIR / filename
    handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def get_console_handler(level: int = logging.INFO) -> logging.StreamHandler:
    """Create a console handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def setup_logging(
    app_name: str = "emai",
    log_level: str = "",
    environment: str = "development",
    enable_console: bool = True,
    enable_file: bool = True,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        app_name: Name of the application (used for log file naming)
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   If empty, auto-determines based on environment
        environment: Application environment (development, production)
        enable_console: Whether to log to console
        enable_file: Whether to log to file

    Returns:
        Configured root logger
    """
    # Auto-determine log level based on environment if not specified
    if not log_level:
        if environment == "production":
            log_level = "WARNING"  # Minimal logging in production
        else:
            log_level = "DEBUG"  # Verbose logging in development

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Add console handler
    if enable_console:
        root_logger.addHandler(get_console_handler(numeric_level))

    # Add file handlers
    if enable_file:
        # Main application log
        root_logger.addHandler(get_file_handler(f"{app_name}.log", logging.DEBUG))

        # Error-only log
        error_handler = get_file_handler(f"{app_name}_error.log", logging.ERROR)
        root_logger.addHandler(error_handler)

    # Configure specific loggers
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Request logging middleware helper
class RequestLogger:
    """Helper class for logging HTTP requests."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        client_ip: str = None,
        user_id: int = None,
    ):
        """Log an HTTP request."""
        extra_info = []
        if client_ip:
            extra_info.append(f"ip={client_ip}")
        if user_id:
            extra_info.append(f"user={user_id}")

        extra_str = " | ".join(extra_info) if extra_info else ""

        if status_code >= 500:
            self.logger.error(
                f"{method} {path} -> {status_code} ({duration_ms:.2f}ms) {extra_str}"
            )
        elif status_code >= 400:
            self.logger.warning(
                f"{method} {path} -> {status_code} ({duration_ms:.2f}ms) {extra_str}"
            )
        else:
            self.logger.info(
                f"{method} {path} -> {status_code} ({duration_ms:.2f}ms) {extra_str}"
            )


# Frontend log handler
class FrontendLogHandler:
    """Handler for logs sent from the frontend."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log(self, level: str, message: str, context: dict = None):
        """
        Log a message from the frontend.

        Args:
            level: Log level (debug, info, warn, error)
            message: Log message
            context: Additional context (user agent, url, etc.)
        """
        context_str = ""
        if context:
            context_parts = [f"{k}={v}" for k, v in context.items()]
            context_str = f" | {' | '.join(context_parts)}"

        full_message = f"[FRONTEND] {message}{context_str}"

        level_map = {
            "debug": self.logger.debug,
            "info": self.logger.info,
            "warn": self.logger.warning,
            "warning": self.logger.warning,
            "error": self.logger.error,
        }

        log_func = level_map.get(level.lower(), self.logger.info)
        log_func(full_message)
