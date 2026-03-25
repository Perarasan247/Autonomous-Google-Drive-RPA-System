"""
MCP Server — FastAPI application exposing all browser, auth, drive, and
filesystem tools as HTTP endpoints consumable by ADK agents.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional
import uvicorn

from utils.logger import get_logger

log = get_logger("MCPServer")

# ── Playwright browser instance (shared across all tool calls) ───────────────
_browser_context = None
_playwright = None
_page = None


def get_page():
    """Return the current playwright page."""
    global _page
    if _page is None:
        raise RuntimeError("Browser not launched. Call /tools/launch_chrome_guest first.")
    return _page


def set_page(page):
    global _page
    _page = page


def set_browser_context(ctx):
    global _browser_context
    _browser_context = ctx


def set_playwright(pw):
    global _playwright
    _playwright = pw


def get_browser_context():
    return _browser_context


def get_playwright():
    return _playwright


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("MCP Server starting up...")
    yield
    # Cleanup on shutdown
    global _browser_context, _playwright, _page
    if _browser_context:
        try:
            await _browser_context.close()
        except Exception:
            pass
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
    log.info("MCP Server shut down cleanly")


app = FastAPI(
    title="RPA MCP Server",
    description="Model Context Protocol server exposing browser and filesystem tools",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Tool response schema ─────────────────────────────────────────────────────

class ToolResponse(BaseModel):
    success: bool
    result: Any = None
    error: Optional[str] = None


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "browser_ready": _page is not None}


# ── Tool listing (MCP discovery) ─────────────────────────────────────────────

@app.get("/tools")
async def list_tools():
    """List all available MCP tools for ADK agent discovery."""
    return {
        "tools": [
            # Browser tools
            {"name": "launch_chrome_guest", "path": "/tools/launch_chrome_guest", "method": "POST"},
            {"name": "navigate_to", "path": "/tools/navigate_to", "method": "POST"},
            {"name": "click_element", "path": "/tools/click_element", "method": "POST"},
            {"name": "type_text", "path": "/tools/type_text", "method": "POST"},
            {"name": "wait_for_element", "path": "/tools/wait_for_element", "method": "POST"},
            {"name": "take_screenshot", "path": "/tools/take_screenshot", "method": "POST"},
            {"name": "get_page_url", "path": "/tools/get_page_url", "method": "POST"},
            {"name": "get_page_content", "path": "/tools/get_page_content", "method": "POST"},
            {"name": "press_key", "path": "/tools/press_key", "method": "POST"},
            # Auth tools
            {"name": "google_login", "path": "/tools/google_login", "method": "POST"},
            {"name": "check_login_status", "path": "/tools/check_login_status", "method": "POST"},
            {"name": "handle_2fa_wait", "path": "/tools/handle_2fa_wait", "method": "POST"},
            # Drive tools
            {"name": "click_my_drive", "path": "/tools/click_my_drive", "method": "POST"},
            {"name": "open_drive_folder", "path": "/tools/open_drive_folder", "method": "POST"},
            {"name": "find_and_download_file", "path": "/tools/find_and_download_file", "method": "POST"},
            {"name": "wait_for_download", "path": "/tools/wait_for_download", "method": "POST"},
            # Filesystem tools
            {"name": "ensure_directory", "path": "/tools/ensure_directory", "method": "POST"},
            {"name": "move_file", "path": "/tools/move_file", "method": "POST"},
            {"name": "watch_for_file", "path": "/tools/watch_for_file", "method": "POST"},
            {"name": "list_directory", "path": "/tools/list_directory", "method": "POST"},
        ]
    }


# ── Import and register all tool routers ────────────────────────────────────
from mcp_server.browser_tools import router as browser_router
from mcp_server.auth_tools import router as auth_router
from mcp_server.drive_tools import router as drive_router
from mcp_server.filesystem_tools import router as fs_router

app.include_router(browser_router, prefix="/tools")
app.include_router(auth_router, prefix="/tools")
app.include_router(drive_router, prefix="/tools")
app.include_router(fs_router, prefix="/tools")


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Start the MCP server (blocking)."""
    uvicorn.run(app, host=host, port=port, log_level="warning")
