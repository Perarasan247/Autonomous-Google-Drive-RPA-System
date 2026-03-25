"""
File system tools — directory creation, file watching, and file moving.
"""
import asyncio
import shutil
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from utils.logger import get_logger
from mcp_server.server import ToolResponse

log = get_logger("FilesystemTools")
router = APIRouter()


class DirectoryRequest(BaseModel):
    path: str


class MoveFileRequest(BaseModel):
    source: str
    destination_dir: str
    create_dest_if_missing: bool = True


class WatchRequest(BaseModel):
    directory: str
    pattern: str
    timeout: int = 120


class ListDirRequest(BaseModel):
    path: str


# ── Watchdog handler ────────────────────────────────────────────────────────

class FileCreatedHandler(FileSystemEventHandler):
    def __init__(self, pattern: str):
        self.pattern = pattern.lower()
        self.found_file: Optional[str] = None

    def on_created(self, event):
        if not event.is_directory:
            fname = Path(event.src_path).name.lower()
            if (
                self.pattern in fname
                and not fname.endswith(".crdownload")
                and not fname.endswith(".tmp")
            ):
                self.found_file = event.src_path
                log.info(f"Watchdog detected new file: {event.src_path}")

    def on_modified(self, event):
        if not event.is_directory:
            fname = Path(event.src_path).name.lower()
            if (
                self.pattern in fname
                and not fname.endswith(".crdownload")
                and not fname.endswith(".tmp")
            ):
                self.found_file = event.src_path


# ── Tool endpoints ───────────────────────────────────────────────────────────

@router.post("/ensure_directory", response_model=ToolResponse)
async def ensure_directory(req: DirectoryRequest):
    """Create a directory (and parents) if it does not already exist."""
    try:
        path = Path(req.path)
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"Directory ensured: {path}")
        return ToolResponse(success=True, result={"path": str(path), "exists": True})
    except Exception as e:
        log.error(f"Failed to create directory {req.path}: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/move_file", response_model=ToolResponse)
async def move_file(req: MoveFileRequest):
    """Move a file from source to destination directory."""
    try:
        src = Path(req.source)
        dest_dir = Path(req.destination_dir)

        if not src.exists():
            return ToolResponse(success=False, error=f"Source file not found: {src}")

        if req.create_dest_if_missing:
            dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / src.name
        shutil.move(str(src), str(dest))
        log.info(f"Moved: {src} → {dest}")
        return ToolResponse(
            success=True,
            result={
                "source": str(src),
                "destination": str(dest),
                "filename": src.name,
            }
        )
    except Exception as e:
        log.error(f"File move failed: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/watch_for_file", response_model=ToolResponse)
async def watch_for_file(req: WatchRequest):
    """
    Use watchdog to monitor a directory for a file matching pattern.
    Returns the file path once found and fully written.
    """
    try:
        directory = Path(req.directory)
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        # First check if file already exists
        existing = [
            f for f in directory.iterdir()
            if req.pattern.lower() in f.name.lower()
            and not f.name.endswith(".crdownload")
            and not f.name.endswith(".tmp")
        ]
        if existing:
            log.info(f"File already exists: {existing[0]}")
            return ToolResponse(success=True, result={"file_path": str(existing[0])})

        # Set up watchdog observer
        handler = FileCreatedHandler(req.pattern)
        observer = Observer()
        observer.schedule(handler, str(directory), recursive=False)
        observer.start()

        log.info(f"Watching {directory} for pattern '{req.pattern}' (timeout: {req.timeout}s)")
        start = time.time()
        try:
            while time.time() - start < req.timeout:
                if handler.found_file:
                    # Wait briefly for file to finish writing
                    await asyncio.sleep(2)
                    observer.stop()
                    observer.join(timeout=5)
                    return ToolResponse(
                        success=True,
                        result={"file_path": handler.found_file}
                    )
                await asyncio.sleep(2)
        finally:
            observer.stop()
            observer.join(timeout=5)

        return ToolResponse(
            success=False,
            error=f"File with pattern '{req.pattern}' not found after {req.timeout}s"
        )

    except Exception as e:
        log.error(f"File watch failed: {e}")
        return ToolResponse(success=False, error=str(e))


@router.post("/list_directory", response_model=ToolResponse)
async def list_directory(req: ListDirRequest):
    """List files in a directory, filtering out temp download files."""
    try:
        path = Path(req.path)
        if not path.exists():
            return ToolResponse(success=True, result={"files": [], "exists": False})

        files = [
            {
                "name": f.name,
                "size_bytes": f.stat().st_size,
                "is_complete": not (f.name.endswith(".crdownload") or f.name.endswith(".tmp")),
            }
            for f in path.iterdir()
            if f.is_file()
        ]
        return ToolResponse(success=True, result={"files": files, "count": len(files)})
    except Exception as e:
        return ToolResponse(success=False, error=str(e))
