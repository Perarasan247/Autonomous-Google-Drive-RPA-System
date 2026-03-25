"""
Browser automation tools using Playwright with stealth.
Exposed as FastAPI routes on the MCP server.
"""
import asyncio
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from utils.logger import get_logger
from utils.error_handler import BrowserError

log = get_logger("BrowserTools")
router = APIRouter()

# Import shared browser state from server module
from mcp_server.server import (
    get_page, set_page, set_browser_context, set_playwright,
    get_browser_context, get_playwright, ToolResponse
)


# ── Request models ───────────────────────────────────────────────────────────

class NavigateRequest(BaseModel):
    url: str
    wait_until: str = "domcontentloaded"
    timeout: int = 30000


class ClickRequest(BaseModel):
    selector: str
    timeout: int = 15000
    force: bool = False


class TypeRequest(BaseModel):
    selector: str
    text: str
    delay: int = 50
    clear_first: bool = True


class WaitRequest(BaseModel):
    selector: str
    timeout: int = 15000
    state: str = "visible"


class KeyRequest(BaseModel):
    key: str


# ── Tool Implementations ─────────────────────────────────────────────────────

@router.post("/launch_chrome_guest", response_model=ToolResponse)
async def launch_chrome_guest():
    """Launch Chrome with a clean guest-like profile using Playwright."""
    try:
        log.info("Launching Chrome in guest mode...")
        pw = await async_playwright().start()
        set_playwright(pw)

        # Use a temp user data dir to simulate guest mode (no saved cookies/passwords)
        user_data_dir = Path("temp_guest_profile")
        user_data_dir.mkdir(exist_ok=True)

        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            channel="chrome",
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions-except=",
                "--window-size=1280,900",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        # Apply stealth patches
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            window.chrome = { runtime: {} };
        """)

        set_browser_context(context)

        page = await context.new_page()
        set_page(page)

        log.info("Chrome launched successfully")
        return ToolResponse(success=True, result={"message": "Chrome launched in guest mode"})

    except Exception as e:
        log.error(f"Failed to launch Chrome: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/navigate_to", response_model=ToolResponse)
async def navigate_to(req: NavigateRequest):
    """Navigate the browser to a URL."""
    try:
        page = get_page()
        log.info(f"Navigating to: {req.url}")
        await page.goto(req.url, wait_until=req.wait_until, timeout=req.timeout * 1000 if req.timeout < 1000 else req.timeout)
        url = page.url
        log.info(f"Navigated to: {url}")
        return ToolResponse(success=True, result={"current_url": url})
    except PWTimeout:
        return ToolResponse(success=False, error=f"Timeout navigating to {req.url}")
    except Exception as e:
        log.error(f"Navigation failed: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/click_element", response_model=ToolResponse)
async def click_element(req: ClickRequest):
    """Click an element by CSS selector or text."""
    try:
        page = get_page()
        log.info(f"Clicking: {req.selector}")
        await page.wait_for_selector(req.selector, state="visible", timeout=req.timeout)
        await page.click(req.selector, force=req.force)
        await asyncio.sleep(0.5)
        return ToolResponse(success=True, result={"clicked": req.selector})
    except PWTimeout:
        return ToolResponse(success=False, error=f"Element not found: {req.selector}")
    except Exception as e:
        log.error(f"Click failed on {req.selector}: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/type_text", response_model=ToolResponse)
async def type_text(req: TypeRequest):
    """Type text into an input element."""
    try:
        page = get_page()
        log.info(f"Typing into: {req.selector}")
        await page.wait_for_selector(req.selector, state="visible", timeout=15000)
        if req.clear_first:
            await page.fill(req.selector, "")
        await page.type(req.selector, req.text, delay=req.delay)
        return ToolResponse(success=True, result={"typed": req.text[:5] + "***"})
    except PWTimeout:
        return ToolResponse(success=False, error=f"Input not found: {req.selector}")
    except Exception as e:
        log.error(f"Type failed: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/wait_for_element", response_model=ToolResponse)
async def wait_for_element(req: WaitRequest):
    """Wait for an element to be in the specified state."""
    try:
        page = get_page()
        log.info(f"Waiting for element: {req.selector} (state={req.state})")
        await page.wait_for_selector(req.selector, state=req.state, timeout=req.timeout)
        return ToolResponse(success=True, result={"found": req.selector})
    except PWTimeout:
        return ToolResponse(success=False, error=f"Timeout waiting for: {req.selector}")
    except Exception as e:
        return ToolResponse(success=False, error=str(e))


@router.post("/take_screenshot", response_model=ToolResponse)
async def take_screenshot():
    """Capture a screenshot of the current page (base64 encoded)."""
    try:
        page = get_page()
        screenshot_dir = Path("logs/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        import time
        path = screenshot_dir / f"screenshot_{int(time.time())}.png"
        await page.screenshot(path=str(path), full_page=False)
        log.info(f"Screenshot saved: {path}")
        return ToolResponse(success=True, result={"path": str(path)})
    except Exception as e:
        return ToolResponse(success=False, error=str(e))


@router.post("/get_page_url", response_model=ToolResponse)
async def get_page_url():
    """Return the current browser URL."""
    try:
        page = get_page()
        return ToolResponse(success=True, result={"url": page.url})
    except Exception as e:
        return ToolResponse(success=False, error=str(e))


@router.post("/get_page_content", response_model=ToolResponse)
async def get_page_content():
    """Return page title and truncated text content for agent context."""
    try:
        page = get_page()
        title = await page.title()
        content = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
        return ToolResponse(success=True, result={"title": title, "content": content})
    except Exception as e:
        return ToolResponse(success=False, error=str(e))


@router.post("/press_key", response_model=ToolResponse)
async def press_key(req: KeyRequest):
    """Press a keyboard key (e.g., Enter, Tab, Escape)."""
    try:
        page = get_page()
        await page.keyboard.press(req.key)
        return ToolResponse(success=True, result={"pressed": req.key})
    except Exception as e:
        return ToolResponse(success=False, error=str(e))
