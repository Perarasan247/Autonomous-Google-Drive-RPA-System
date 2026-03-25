"""
File System Agent — Google ADK LlmAgent for handling downloaded files.
Responsible for: watching download completion, moving file to destination.
"""
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from config import settings
from utils.logger import get_logger

log = get_logger("FilesystemAgent")
BASE_URL = settings.mcp_base_url


async def _call(endpoint: str, payload: dict = None) -> dict:
    import os
    if os.getenv("MOCK_MCP") == "true":
        return {"status": "success", "mock": True, "endpoint": endpoint}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/tools/{endpoint}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


async def ensure_directory(path: str) -> dict:
    """
    Create a directory and all parent directories if they don't exist.

    Args:
        path: Full directory path to create (e.g. D:\\test)
    """
    log.info(f"Tool call: ensure_directory '{path}'")
    return await _call("ensure_directory", {"path": path})


async def watch_for_file(directory: str, pattern: str, timeout: int = 120) -> dict:
    """
    Watch a directory for a new file matching a name pattern.
    Returns the full file path once found.

    Args:
        directory: Directory to watch (e.g. D:\\Projects\\Download)
        pattern: Partial filename to match (case-insensitive)
        timeout: Max seconds to wait
    """
    log.info(f"Tool call: watch_for_file in '{directory}' pattern='{pattern}'")
    return await _call("watch_for_file", {"directory": directory, "pattern": pattern, "timeout": timeout})


async def list_directory(path: str) -> dict:
    """
    List files in a directory.

    Args:
        path: Directory path to list
    """
    log.info(f"Tool call: list_directory '{path}'")
    return await _call("list_directory", {"path": path})


async def move_file(source: str, destination_dir: str) -> dict:
    """
    Move a file from source path to a destination directory.
    Creates the destination directory if it doesn't exist.

    Args:
        source: Full path to the source file
        destination_dir: Directory to move the file into
    """
    log.info(f"Tool call: move_file '{source}' -> '{destination_dir}'")
    return await _call("move_file", {
        "source": source,
        "destination_dir": destination_dir,
        "create_dest_if_missing": True,
    })


# ── Agent definition ─────────────────────────────────────────────────────────

filesystem_agent = LlmAgent(
    name="FileSystemAgent",
    model="gemini-2.0-flash",
    description=(
        "Monitors the download directory for a completed PDF download, then "
        f"moves it from {settings.download_dir} to {settings.destination_dir}."
    ),
    instruction=f"""You are a file system management specialist.

Your task:
1. Ensure the destination directory exists: call ensure_directory('{settings.destination_dir}')
2. Watch for the downloaded file: call watch_for_file(
       directory='{settings.download_dir}',
       pattern='{settings.target_file_name}',
       timeout={settings.download_timeout}
   )
3. If file found, list the download directory to confirm: call list_directory('{settings.download_dir}')
4. Move the file: call move_file(source=<full_path_from_step_2>, destination_dir='{settings.destination_dir}')
5. Confirm by listing destination: call list_directory('{settings.destination_dir}')
6. Report success with final file location

Error handling:
- If file not found after timeout, check if download path is correct using list_directory
- If move fails (permissions), report the exact error
- If destination directory creation fails, report and stop

Success means:
- The PDF is confirmed to be in: {settings.destination_dir}
- Report the full final file path
""",
    tools=[
        FunctionTool(ensure_directory),
        FunctionTool(watch_for_file),
        FunctionTool(list_directory),
        FunctionTool(move_file),
    ],
)
