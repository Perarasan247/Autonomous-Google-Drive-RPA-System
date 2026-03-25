"""
Google Drive navigation and download tools.
"""
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from utils.logger import get_logger
from mcp_server.server import get_page, ToolResponse

log = get_logger("DriveTools")
router = APIRouter()


class FolderRequest(BaseModel):
    folder_name: str
    timeout: int = 15000


class DownloadRequest(BaseModel):
    filename_pattern: str
    download_dir: str = r"D:\Projects\Download"
    timeout: int = 120


class WaitDownloadRequest(BaseModel):
    download_dir: str
    filename_pattern: str
    timeout: int = 120


@router.post("/click_my_drive", response_model=ToolResponse)
async def click_my_drive():
    """Click 'My Drive' in the Google Drive left sidebar."""
    try:
        page = get_page()
        log.info("Clicking 'My Drive' in sidebar...")

        selectors = [
            'a[href*="my-drive"]',
            '[data-tooltip="My Drive"]',
            'text="My Drive"',
            '[aria-label="My Drive"]',
            'div[data-root="true"]',
        ]

        for sel in selectors:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    await elem.click()
                    log.info("Clicked 'My Drive'")
                    await asyncio.sleep(2)
                    return ToolResponse(success=True, result={"clicked": "My Drive"})
            except Exception:
                continue

        # Fallback: navigate directly
        log.info("Trying direct My Drive URL...")
        await page.goto("https://drive.google.com/drive/my-drive", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        return ToolResponse(success=True, result={"clicked": "My Drive (direct URL)"}  )

    except Exception as e:
        log.error(f"Failed to click My Drive: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/open_drive_folder", response_model=ToolResponse)
async def open_drive_folder(req: FolderRequest):
    """
    Find and open a folder by name in Google Drive.
    Tries double-click and Enter key approaches.
    """
    try:
        page = get_page()
        log.info(f"Opening folder: {req.folder_name}")
        await asyncio.sleep(1)

        # Strategy 1: Find by aria-label containing folder name
        selectors = [
            f'[aria-label*="{req.folder_name}"]',
            f'[data-tooltip="{req.folder_name}"]',
            f'div[data-name="{req.folder_name}"]',
        ]

        for sel in selectors:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    await elem.dblclick()
                    log.info(f"Double-clicked folder: {req.folder_name}")
                    await asyncio.sleep(2)
                    return ToolResponse(success=True, result={"opened_folder": req.folder_name})
            except Exception:
                continue

        # Strategy 2: Find via text content
        try:
            folder_elem = await page.get_by_text(req.folder_name, exact=True).first.element_handle()
            if folder_elem:
                await folder_elem.dblclick()
                await asyncio.sleep(2)
                return ToolResponse(success=True, result={"opened_folder": req.folder_name})
        except Exception:
            pass

        # Strategy 3: Evaluate DOM to find by folder name
        found = await page.evaluate(f"""
            () => {{
                const items = document.querySelectorAll('[data-id]');
                for (const item of items) {{
                    if (item.textContent.includes('{req.folder_name}')) {{
                        item.dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}));
                        return true;
                    }}
                }}
                return false;
            }}
        """)

        if found:
            await asyncio.sleep(2)
            return ToolResponse(success=True, result={"opened_folder": req.folder_name})

        return ToolResponse(
            success=False,
            error=f"Folder '{req.folder_name}' not found in current view"
        )

    except Exception as e:
        log.error(f"Failed to open folder {req.folder_name}: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/find_and_download_file", response_model=ToolResponse)
async def find_and_download_file(req: DownloadRequest):
    """
    Find a file by name pattern and trigger its download via right-click menu.
    """
    try:
        page = get_page()
        log.info(f"Looking for file matching: {req.filename_pattern}")
        await asyncio.sleep(1)

        # Ensure download directory exists
        Path(req.download_dir).mkdir(parents=True, exist_ok=True)

        # Strategy 1: Find by aria-label
        file_elem = None
        selectors = [
            f'[aria-label*="{req.filename_pattern}"]',
            f'[data-tooltip*="{req.filename_pattern}"]',
        ]
        for sel in selectors:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    file_elem = elem
                    break
            except Exception:
                continue

        # Strategy 2: Scan via text
        if not file_elem:
            try:
                file_elem = await page.get_by_text(req.filename_pattern).first.element_handle()
            except Exception:
                pass

        # Strategy 3: JavaScript scan
        if not file_elem:
            found = await page.evaluate(f"""
                () => {{
                    const items = document.querySelectorAll('[data-id]');
                    for (const item of items) {{
                        if (item.textContent.includes('{req.filename_pattern}')) {{
                            item.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
            if not found:
                return ToolResponse(
                    success=False,
                    error=f"File '{req.filename_pattern}' not found"
                )
            await asyncio.sleep(0.5)
            # Right-click via keyboard shortcut after selection
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
        else:
            await file_elem.click()
            await asyncio.sleep(0.5)

        # Right-click to get context menu
        if file_elem:
            await file_elem.click(button="right")
        else:
            await page.keyboard.press("ContextMenu")

        await asyncio.sleep(1)

        # Click Download in context menu
        download_menu_selectors = [
            'text="Download"',
            '[aria-label="Download"]',
            'div[data-action="download"]',
            'li:has-text("Download")',
        ]

        async with page.expect_download(timeout=req.timeout * 1000) as download_info:
            for sel in download_menu_selectors:
                try:
                    elem = await page.query_selector(sel)
                    if elem:
                        await elem.click()
                        break
                except Exception:
                    continue

        download = await download_info.value
        suggested_name = download.suggested_filename
        save_path = Path(req.download_dir) / suggested_name
        await download.save_as(str(save_path))

        log.info(f"File downloaded to: {save_path}")
        return ToolResponse(
            success=True,
            result={
                "downloaded_file": str(save_path),
                "filename": suggested_name,
            }
        )

    except Exception as e:
        log.error(f"Download failed: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/wait_for_download", response_model=ToolResponse)
async def wait_for_download(req: WaitDownloadRequest):
    """Poll the download directory until a matching file appears (not .crdownload)."""
    import time
    import glob

    log.info(f"Watching {req.download_dir} for pattern: {req.filename_pattern}")
    download_dir = Path(req.download_dir)
    start = time.time()

    while time.time() - start < req.timeout:
        matches = list(download_dir.glob(f"*{req.filename_pattern}*"))
        complete = [
            f for f in matches
            if not str(f).endswith(".crdownload") and not str(f).endswith(".tmp")
        ]
        if complete:
            file_path = str(complete[0])
            log.info(f"Download complete: {file_path}")
            return ToolResponse(success=True, result={"file_path": file_path})
        await asyncio.sleep(3)

    return ToolResponse(
        success=False,
        error=f"No file matching '{req.filename_pattern}' found in {req.download_dir} after {req.timeout}s"
    )
