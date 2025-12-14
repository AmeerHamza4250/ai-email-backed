"""
Structured logging utility.
"""
import structlog
import logging
import sys
from typing import Any

# Configure structlog with console-friendly output
try:
    # Try to use ConsoleRenderer for pretty output
    from structlog.dev import ConsoleRenderer
    renderer = ConsoleRenderer()
except ImportError:
    # Fallback to KeyValueRenderer if ConsoleRenderer not available
    from structlog.processors import KeyValueRenderer
    renderer = KeyValueRenderer()

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        renderer,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Configure standard logging
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)


def get_logger(name: str = __name__) -> Any:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return structlog.get_logger(name)

