"""
Structured logger using loguru — outputs to console (rich) and log file.
"""
import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Remove default loguru handler
logger.remove()

# Console handler — rich coloured output
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[agent]: <20}</cyan> | {message}",
    level="INFO",
    colorize=True,
)

# File handler — full detail
logger.add(
    LOG_DIR / "rpa.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[agent]: <20} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    enqueue=True,
)


def get_logger(agent_name: str):
    """Return a logger instance bound to a specific agent name."""
    return logger.bind(agent=agent_name)
