"""
Configuration module — loads all settings from .env
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Google Credentials ──────────────────────────────────────────────────
    google_email: str = Field(..., env="GOOGLE_EMAIL")
    google_password: str = Field(..., env="GOOGLE_PASSWORD")

    # ── Gemini API ──────────────────────────────────────────────────────────
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")

    # ── File Paths ──────────────────────────────────────────────────────────
    download_dir: Path = Field(default=Path(r"D:\Projects\Download"), env="DOWNLOAD_DIR")
    destination_dir: Path = Field(default=Path(r"D:\test"), env="DESTINATION_DIR")

    # ── Target ──────────────────────────────────────────────────────────────
    target_folder: str = Field(default="Coursera Certificates", env="TARGET_FOLDER")
    target_file_name: str = Field(
        default="NVIDIA Fundamentals of Deep Learning", env="TARGET_FILE_NAME"
    )

    # ── MCP Server ──────────────────────────────────────────────────────────
    mcp_server_host: str = Field(default="127.0.0.1", env="MCP_SERVER_HOST")
    mcp_server_port: int = Field(default=8765, env="MCP_SERVER_PORT")

    # ── Timeouts ────────────────────────────────────────────────────────────
    page_load_timeout: int = Field(default=30, env="PAGE_LOAD_TIMEOUT")
    login_timeout: int = Field(default=60, env="LOGIN_TIMEOUT")
    download_timeout: int = Field(default=120, env="DOWNLOAD_TIMEOUT")
    element_wait_timeout: int = Field(default=15, env="ELEMENT_WAIT_TIMEOUT")

    # ── Retry ───────────────────────────────────────────────────────────────
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_delay: int = Field(default=2, env="RETRY_DELAY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def mcp_base_url(self) -> str:
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}"


# Singleton instance — import this everywhere
settings = Settings()
