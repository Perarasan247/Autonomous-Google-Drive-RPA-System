"""
Shared execution state manager — single source of truth for all agents.
"""
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from utils.logger import get_logger

log = get_logger("StateManager")


class LoginStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_2FA = "awaiting_2fa"
    SUCCESS = "success"
    FAILED = "failed"


class DownloadStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionState:
    # Browser state
    browser_launched: bool = False
    current_url: str = ""

    # Auth state
    login_status: LoginStatus = LoginStatus.NOT_STARTED

    # Drive navigation state
    in_my_drive: bool = False
    current_folder: str = ""
    target_file_found: bool = False

    # Download state
    download_status: DownloadStatus = DownloadStatus.NOT_STARTED
    downloaded_file_path: str = ""

    # File system state
    destination_ready: bool = False
    file_moved: bool = False

    # Error tracking
    last_error: str = ""
    retry_count: int = 0


class StateManager:
    """Thread-safe singleton state manager."""

    _instance: Optional["StateManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._state = ExecutionState()
        return cls._instance

    @property
    def state(self) -> ExecutionState:
        return self._state

    def update(self, **kwargs) -> None:
        """Update one or more state fields."""
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                old = getattr(self._state, key)
                setattr(self._state, key, value)
                log.debug(f"State: {key} = {old!r} → {value!r}")
            else:
                log.warning(f"Unknown state field: {key}")

    def reset(self) -> None:
        """Reset state for a fresh run."""
        self._state = ExecutionState()
        log.info("State reset for new run")

    def to_dict(self) -> dict:
        """Export state as a dictionary for ADK session context."""
        return {
            "browser_launched": self._state.browser_launched,
            "current_url": self._state.current_url,
            "login_status": self._state.login_status.value,
            "in_my_drive": self._state.in_my_drive,
            "current_folder": self._state.current_folder,
            "target_file_found": self._state.target_file_found,
            "download_status": self._state.download_status.value,
            "downloaded_file_path": self._state.downloaded_file_path,
            "destination_ready": self._state.destination_ready,
            "file_moved": self._state.file_moved,
            "last_error": self._state.last_error,
            "retry_count": self._state.retry_count,
        }


# Singleton instance
state_manager = StateManager()
