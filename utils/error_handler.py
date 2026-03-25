"""
Error handling utilities — custom exceptions and retry decorator.
"""
import asyncio
import functools
import time
from typing import Callable, Type
from utils.logger import get_logger

log = get_logger("ErrorHandler")


# ── Custom Exceptions ───────────────────────────────────────────────────────

class RPAError(Exception):
    """Base exception for all RPA errors."""
    pass


class BrowserError(RPAError):
    """Browser launch or navigation failed."""
    pass


class AuthenticationError(RPAError):
    """Login failed — wrong credentials or CAPTCHA blocked."""
    pass


class TwoFactorRequired(RPAError):
    """Google requires 2FA — waiting for manual completion."""
    pass


class DriveNavigationError(RPAError):
    """Could not find folder or file in Google Drive."""
    pass


class DownloadError(RPAError):
    """File download did not complete within timeout."""
    pass


class FileSystemError(RPAError):
    """File move or directory creation failed."""
    pass


class MCPConnectionError(RPAError):
    """Could not connect to MCP server."""
    pass


# ── Retry Decorator ──────────────────────────────────────────────────────────

def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (RPAError,),
    agent: str = "Retry",
):
    """
    Decorator that retries a sync or async function on specified exceptions.

    Usage:
        @retry(max_attempts=3, delay=2)
        async def my_func(): ...
    """
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                _log = get_logger(agent or func.__module__)
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts:
                            _log.error(f"[{func.__name__}] Failed after {max_attempts} attempts: {e}")
                            raise
                        _log.warning(
                            f"[{func.__name__}] Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                _log = get_logger(agent or func.__module__)
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts:
                            _log.error(f"[{func.__name__}] Failed after {max_attempts} attempts: {e}")
                            raise
                        _log.warning(
                            f"[{func.__name__}] Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
            return sync_wrapper
    return decorator
