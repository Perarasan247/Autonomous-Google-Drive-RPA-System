"""
Google authentication tools — handles login flow including 2FA detection.
"""
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from utils.logger import get_logger
from mcp_server.server import get_page, ToolResponse

log = get_logger("AuthTools")
router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str
    timeout: int = 60


class TwoFARequest(BaseModel):
    timeout: int = 120


@router.post("/google_login", response_model=ToolResponse)
async def google_login(req: LoginRequest):
    """
    Complete Google login flow:
    1. Navigate to accounts.google.com
    2. Enter email → Next
    3. Enter password → Next
    4. Detect outcome: success, 2FA, or failure
    """
    try:
        page = get_page()
        log.info("Starting Google login flow...")

        # Step 1: Navigate to Google sign-in
        await page.goto(
            "https://accounts.google.com/signin/v2/identifier",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(2)

        # Step 2: Enter email
        log.info("Entering email...")
        email_selectors = [
            'input[type="email"]',
            '#identifierId',
            'input[name="identifier"]',
        ]
        for sel in email_selectors:
            try:
                await page.wait_for_selector(sel, state="visible", timeout=5000)
                await page.fill(sel, req.email)
                break
            except Exception:
                continue

        # Click Next
        await asyncio.sleep(0.5)
        next_selectors = ['#identifierNext', 'button:has-text("Next")', '[jsname="LgbsSe"]']
        for sel in next_selectors:
            try:
                await page.click(sel, timeout=5000)
                break
            except Exception:
                continue

        # Step 3: Wait for password field
        log.info("Waiting for password field...")
        await asyncio.sleep(2)
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            '#password input',
        ]
        for sel in password_selectors:
            try:
                await page.wait_for_selector(sel, state="visible", timeout=10000)
                await page.fill(sel, req.password)
                break
            except Exception:
                continue

        # Click Next (sign in)
        await asyncio.sleep(0.5)
        next_pw_selectors = ['#passwordNext', 'button:has-text("Next")', 'button[type="submit"]']
        for sel in next_pw_selectors:
            try:
                await page.click(sel, timeout=5000)
                break
            except Exception:
                continue

        # Step 4: Wait and detect outcome
        log.info("Waiting for login result...")
        await asyncio.sleep(3)

        current_url = page.url

        # Check for 2FA
        try:
            await page.wait_for_selector(
                'text="2-Step Verification", text="Verify it\'s you", input[name="totpPin"]',
                timeout=5000
            )
            log.warning("2FA required! Waiting for manual completion...")
            return ToolResponse(
                success=False,
                result={"status": "2fa_required", "url": current_url},
                error="2FA required — please complete verification manually"
            )
        except Exception:
            pass

        # Check for wrong password
        try:
            wrong_pw = await page.query_selector('text="Wrong password"')
            if wrong_pw:
                return ToolResponse(success=False, error="Wrong password")
        except Exception:
            pass

        # Check for success — should redirect away from accounts.google.com
        if "myaccount.google.com" in current_url or "drive.google.com" in current_url:
            log.info("Login successful!")
            return ToolResponse(success=True, result={"status": "logged_in", "url": current_url})

        # Wait a bit more and re-check
        await asyncio.sleep(3)
        current_url = page.url
        if "accounts.google.com" not in current_url:
            log.info(f"Login appears successful. URL: {current_url}")
            return ToolResponse(success=True, result={"status": "logged_in", "url": current_url})

        return ToolResponse(
            success=False,
            error=f"Login outcome unclear. Current URL: {current_url}"
        )

    except Exception as e:
        log.error(f"Login failed with exception: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/check_login_status", response_model=ToolResponse)
async def check_login_status():
    """Check if the user is currently logged into Google."""
    try:
        page = get_page()
        current_url = page.url

        # Try to find user avatar/profile button
        try:
            avatar = await page.query_selector('[data-email], [aria-label*="Google Account"]')
            if avatar:
                return ToolResponse(success=True, result={"logged_in": True, "url": current_url})
        except Exception:
            pass

        # Check URL-based signals
        if "accounts.google.com/signin" in current_url:
            return ToolResponse(success=True, result={"logged_in": False, "url": current_url})

        return ToolResponse(success=True, result={"logged_in": True, "url": current_url})

    except Exception as e:
        return ToolResponse(success=False, error=str(e))


@router.post("/handle_2fa_wait", response_model=ToolResponse)
async def handle_2fa_wait(req: TwoFARequest):
    """
    Wait for the user to manually complete 2FA.
    Polls for successful login redirect every 5 seconds.
    """
    try:
        page = get_page()
        log.warning(f"Waiting up to {req.timeout}s for manual 2FA completion...")

        elapsed = 0
        while elapsed < req.timeout:
            await asyncio.sleep(5)
            elapsed += 5
            current_url = page.url
            if "accounts.google.com" not in current_url:
                log.info(f"2FA completed! Redirected to: {current_url}")
                return ToolResponse(
                    success=True,
                    result={"status": "2fa_complete", "url": current_url}
                )

        return ToolResponse(
            success=False,
            error=f"2FA not completed within {req.timeout} seconds"
        )

    except Exception as e:
        return ToolResponse(success=False, error=str(e))
