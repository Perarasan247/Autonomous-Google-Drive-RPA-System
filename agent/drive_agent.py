"""
Drive Navigation Agent — Google ADK LlmAgent for navigating Google Drive.
Responsible for: My Drive → Coursera Certificates → download target PDF.
"""
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from config import settings
from utils.logger import get_logger

log = get_logger("DriveAgent")
BASE_URL = settings.mcp_base_url


async def _call(endpoint: str, payload: dict = None) -> dict:
    import os
    if os.getenv("MOCK_MCP") == "true":
        return {"status": "success", "mock": True, "endpoint": endpoint}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/tools/{endpoint}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


async def navigate_to_drive() -> dict:
    """Navigate the browser to Google Drive (https://drive.google.com/)."""
    log.info("Tool call: navigate to Google Drive")
    return await _call("navigate_to", {"url": "https://drive.google.com/", "wait_until": "domcontentloaded"})


async def click_my_drive() -> dict:
    """Click 'My Drive' in the Google Drive left sidebar."""
    log.info("Tool call: click_my_drive")
    return await _call("click_my_drive")


async def open_drive_folder(folder_name: str) -> dict:
    """
    Open a folder in Google Drive by name (double-click).

    Args:
        folder_name: Exact or partial name of the folder to open
    """
    log.info(f"Tool call: open_drive_folder '{folder_name}'")
    return await _call("open_drive_folder", {"folder_name": folder_name, "timeout": 15000})


async def find_and_download_file(filename_pattern: str) -> dict:
    """
    Locate a file by name pattern and trigger its download.

    Args:
        filename_pattern: Partial filename to search for (case-insensitive)
    """
    log.info(f"Tool call: find_and_download_file '{filename_pattern}'")
    return await _call("find_and_download_file", {
        "filename_pattern": filename_pattern,
        "download_dir": str(settings.download_dir),
        "timeout": settings.download_timeout,
    })


async def wait_for_download(filename_pattern: str) -> dict:
    """
    Wait for a file matching the pattern to appear in the download directory.

    Args:
        filename_pattern: Partial filename to look for
    """
    log.info(f"Tool call: wait_for_download '{filename_pattern}'")
    return await _call("wait_for_download", {
        "download_dir": str(settings.download_dir),
        "filename_pattern": filename_pattern,
        "timeout": settings.download_timeout,
    })


async def get_page_content() -> dict:
    """Get current page title and content to understand current Drive state."""
    return await _call("get_page_content")


async def take_screenshot() -> dict:
    """Take a screenshot to see current Drive state."""
    return await _call("take_screenshot")


# ── Agent definition ─────────────────────────────────────────────────────────

drive_agent = LlmAgent(
    name="DriveNavigationAgent",
    model="gemini-2.0-flash",
    description=(
        "Navigates Google Drive, opens the Coursera Certificates folder, "
        f"and downloads the file matching '{settings.target_file_name}'."
    ),
    instruction=f"""You are a Google Drive navigation specialist.

Your task:
1. Navigate to Google Drive: call navigate_to_drive()
2. Wait for Drive to load (check page content)
3. Click 'My Drive': call click_my_drive()
4. Open the folder '{settings.target_folder}': call open_drive_folder('{settings.target_folder}')
5. Find and download '{settings.target_file_name}': call find_and_download_file('{settings.target_file_name}')
6. Wait for download to complete: call wait_for_download('{settings.target_file_name}')

Important:
- Take a screenshot if you're unsure of the current state
- If a folder isn't found first try, use get_page_content() to understand what's visible
- The download goes to: {settings.download_dir}
- Report the full path of the downloaded file upon success

Error handling:
- If 'Coursera Certificates' folder is not visible, it might need scrolling — try Open Drive Folder again
- If the file download fails, try right-clicking → Download as an alternative
""",
    tools=[
        FunctionTool(navigate_to_drive),
        FunctionTool(click_my_drive),
        FunctionTool(open_drive_folder),
        FunctionTool(find_and_download_file),
        FunctionTool(wait_for_download),
        FunctionTool(get_page_content),
        FunctionTool(take_screenshot),
    ],
)
