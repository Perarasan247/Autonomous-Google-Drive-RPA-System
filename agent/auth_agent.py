"""
Authentication Agent — Google ADK LlmAgent for Google account login.
Responsible for: email/password entry, 2FA detection, login verification.
"""
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from config import settings
from utils.logger import get_logger

log = get_logger("AuthAgent")
BASE_URL = settings.mcp_base_url


async def _call(endpoint: str, payload: dict = None) -> dict:
    import os
    if os.getenv("MOCK_MCP") == "true":
        return {"status": "success", "mock": True, "endpoint": endpoint}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/tools/{endpoint}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


async def google_login(email: str, password: str) -> dict:
    """
    Perform full Google login flow: enter email, enter password, handle redirects.

    Args:
        email: Google account email address
        password: Google account password
    Returns:
        Dict with 'success' and 'result.status' ('logged_in' or '2fa_required')
    """
    log.info(f"Tool call: google_login for {email[:4]}***")
    return await _call("google_login", {"email": email, "password": password})


async def check_login_status() -> dict:
    """Check if the user is currently logged into Google by inspecting the page."""
    log.info("Tool call: check_login_status")
    return await _call("check_login_status")


async def handle_2fa_wait(timeout: int = 120) -> dict:
    """
    Wait for the user to complete 2-Factor Authentication manually.
    Polls for up to `timeout` seconds until login redirect is detected.

    Args:
        timeout: Number of seconds to wait for manual 2FA completion
    """
    log.info(f"Tool call: handle_2fa_wait (timeout={timeout}s)")
    return await _call("handle_2fa_wait", {"timeout": timeout})


# ── Agent definition ─────────────────────────────────────────────────────────

auth_agent = LlmAgent(
    name="AuthenticationAgent",
    model="gemini-2.0-flash",
    description=(
        "Handles Google account authentication. Enters email and password, "
        "detects 2FA requirements, and waits for successful login."
    ),
    instruction=f"""You are a Google authentication specialist.

Your job is to log in to Google with these credentials:
- Email: {settings.google_email}
- Password: (use the google_login tool — password is pre-configured)

Login procedure:
1. Call google_login(email="{settings.google_email}", password="<from config>") with the actual password from config
2. If result shows 'logged_in' → success, report success
3. If result shows '2fa_required' → call handle_2fa_wait(timeout=120)
   - This pauses for the user to complete 2FA manually
   - After it returns success, report that login is complete
4. If result shows an error (wrong password, CAPTCHA) → report the error clearly

After successful login, the session will be maintained in the browser for subsequent agents.

IMPORTANT: Never log or display the full password. Always call google_login with the 
credentials provided: email="{settings.google_email}" and password="{settings.google_password}"
""",
    tools=[
        FunctionTool(google_login),
        FunctionTool(check_login_status),
        FunctionTool(handle_2fa_wait),
    ],
)
