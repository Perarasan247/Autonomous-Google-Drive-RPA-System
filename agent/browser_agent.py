"""
Browser Automation Agent — Google ADK LlmAgent wrapping all browser MCP tools.
Responsible for: launching Chrome, navigating URLs, clicking, typing.
"""
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from config import settings
from utils.logger import get_logger

log = get_logger("BrowserAgent")
BASE_URL = settings.mcp_base_url


# ── MCP Tool wrappers ────────────────────────────────────────────────────────

async def _call(endpoint: str, payload: dict = None) -> dict:
    """Call an MCP server endpoint and return the JSON response."""
    import os
    if os.getenv("MOCK_MCP") == "true":
        return {"status": "success", "mock": True, "endpoint": endpoint}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/tools/{endpoint}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


async def launch_chrome_guest() -> dict:
    """Launch Chrome browser in guest mode with stealth settings."""
    log.info("Tool call: launch_chrome_guest")
    return await _call("launch_chrome_guest")


async def navigate_to(url: str, wait_until: str = "domcontentloaded") -> dict:
    """
    Navigate the browser to a URL.

    Args:
        url: Full URL to navigate to (e.g. https://drive.google.com)
        wait_until: When to consider navigation done. Use 'domcontentloaded' for speed.
    """
    log.info(f"Tool call: navigate_to {url}")
    return await _call("navigate_to", {"url": url, "wait_until": wait_until})


async def click_element(selector: str, timeout: int = 15000) -> dict:
    """
    Click a page element identified by a CSS selector.

    Args:
        selector: CSS selector or text selector (e.g. 'button:has-text("Next")')
        timeout: Max milliseconds to wait for element. Default 15000.
    """
    log.info(f"Tool call: click_element {selector}")
    return await _call("click_element", {"selector": selector, "timeout": timeout})


async def type_text(selector: str, text: str, delay: int = 50) -> dict:
    """
    Type text into a form field.

    Args:
        selector: CSS selector of the input field
        text: Text to type
        delay: Milliseconds between keystrokes (simulates human typing)
    """
    log.info(f"Tool call: type_text into {selector}")
    return await _call("type_text", {"selector": selector, "text": text, "delay": delay})


async def wait_for_element(selector: str, timeout: int = 15000, state: str = "visible") -> dict:
    """
    Wait for an element to appear on the page.

    Args:
        selector: CSS selector to wait for
        timeout: Max milliseconds to wait
        state: 'visible', 'hidden', 'attached', or 'detached'
    """
    log.info(f"Tool call: wait_for_element {selector}")
    return await _call("wait_for_element", {"selector": selector, "timeout": timeout, "state": state})


async def take_screenshot() -> dict:
    """Capture a screenshot of the current browser page for debugging."""
    log.info("Tool call: take_screenshot")
    return await _call("take_screenshot")


async def get_page_url() -> dict:
    """Get the current URL of the browser."""
    return await _call("get_page_url")


async def get_page_content() -> dict:
    """Get the current page title and text content for context."""
    return await _call("get_page_content")


async def press_key(key: str) -> dict:
    """
    Press a keyboard key.

    Args:
        key: Key name (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown')
    """
    return await _call("press_key", {"key": key})


# ── Agent definition ─────────────────────────────────────────────────────────

browser_agent = LlmAgent(
    name="BrowserAutomationAgent",
    model="gemini-2.0-flash",
    description=(
        "Controls the Chrome browser. Can launch Chrome in guest mode, navigate to URLs, "
        "click elements, type text, and capture screenshots. Use this agent for all "
        "browser interaction tasks."
    ),
    instruction="""You are a browser automation specialist. You control a Chrome browser using Playwright.

Your capabilities:
- Launch Chrome in guest mode (no saved passwords/cookies)
- Navigate to any URL
- Click buttons, links, and other elements
- Type text into input fields
- Wait for elements to appear
- Take screenshots for debugging
- Get current page URL and content

When performing tasks:
1. Always take a screenshot if something unexpected happens
2. Wait for elements before clicking them
3. If a selector fails, try alternative selectors
4. Report success or failure clearly with the current URL

You communicate results as JSON with 'success' and 'result' or 'error' fields.
""",
    tools=[
        FunctionTool(launch_chrome_guest),
        FunctionTool(navigate_to),
        FunctionTool(click_element),
        FunctionTool(type_text),
        FunctionTool(wait_for_element),
        FunctionTool(take_screenshot),
        FunctionTool(get_page_url),
        FunctionTool(get_page_content),
        FunctionTool(press_key),
    ],
)
