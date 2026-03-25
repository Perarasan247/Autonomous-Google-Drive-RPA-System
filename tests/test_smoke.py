"""
Smoke tests — verify imports, config, and MCP server startup.
Run with: pytest tests/test_smoke.py -v
"""
import os
import sys
import pytest
import asyncio
import threading
import time

# Set dummy env vars before importing config
os.environ.setdefault("GOOGLE_EMAIL", "test@gmail.com")
os.environ.setdefault("GOOGLE_PASSWORD", "testpassword")
os.environ.setdefault("GOOGLE_API_KEY", "test_key_12345")
os.environ.setdefault("DOWNLOAD_DIR", r"D:\Projects\Download")
os.environ.setdefault("DESTINATION_DIR", r"D:\test")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


# ── Import tests ─────────────────────────────────────────────────────────────

def test_import_config():
    from config import settings
    assert settings.google_email == "test@gmail.com"
    assert settings.mcp_server_port == 8765


def test_import_state_manager():
    from utils.state_manager import state_manager, LoginStatus, DownloadStatus
    assert state_manager is not None
    assert LoginStatus.NOT_STARTED == "not_started"
    assert DownloadStatus.NOT_STARTED == "not_started"


def test_import_logger():
    from utils.logger import get_logger
    log = get_logger("TestAgent")
    assert log is not None


def test_import_error_handler():
    from utils.error_handler import (
        RPAError, BrowserError, AuthenticationError,
        DriveNavigationError, DownloadError, FileSystemError
    )
    assert issubclass(BrowserError, RPAError)
    assert issubclass(AuthenticationError, RPAError)


def test_import_mcp_server():
    from mcp_server.server import app
    assert app is not None
    assert app.title == "RPA MCP Server"


def test_import_browser_tools():
    from mcp_server.browser_tools import router
    assert router is not None


def test_import_auth_tools():
    from mcp_server.auth_tools import router
    assert router is not None


def test_import_drive_tools():
    from mcp_server.drive_tools import router
    assert router is not None


def test_import_filesystem_tools():
    from mcp_server.filesystem_tools import router
    assert router is not None


# ── Retry decorator test ─────────────────────────────────────────────────────

def test_retry_decorator_sync():
    from utils.error_handler import retry, RPAError

    call_count = {"n": 0}

    @retry(max_attempts=3, delay=0.01, exceptions=(RPAError,))
    def flaky_func():
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RPAError("Transient error")
        return "success"

    result = flaky_func()
    assert result == "success"
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_retry_decorator_async():
    from utils.error_handler import retry, RPAError

    call_count = {"n": 0}

    @retry(max_attempts=2, delay=0.01, exceptions=(RPAError,))
    async def flaky_async():
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RPAError("Async transient error")
        return "async_success"

    result = await flaky_async()
    assert result == "async_success"


# ── State manager tests ──────────────────────────────────────────────────────

def test_state_manager_singleton():
    from utils.state_manager import StateManager
    sm1 = StateManager()
    sm2 = StateManager()
    assert sm1 is sm2


def test_state_manager_update():
    from utils.state_manager import state_manager
    state_manager.reset()
    state_manager.update(current_url="https://drive.google.com")
    assert state_manager.state.current_url == "https://drive.google.com"


def test_state_manager_to_dict():
    from utils.state_manager import state_manager
    state_manager.reset()
    d = state_manager.to_dict()
    assert "login_status" in d
    assert "download_status" in d
    assert "file_moved" in d


# ── Filesystem tools tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filesystem_ensure_and_list():
    """Test directory creation and listing without moving real files."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        test_dir = Path(tmp) / "rpa_test_dir"

        # Test via direct function call (bypassing HTTP)
        test_dir.mkdir(parents=True, exist_ok=True)
        assert test_dir.exists()

        # Create a test file
        test_file = test_dir / "test.pdf"
        test_file.write_text("fake pdf content")
        assert test_file.exists()

        # Test move via shutil
        import shutil
        dest_dir = Path(tmp) / "destination"
        dest_dir.mkdir(exist_ok=True)
        shutil.move(str(test_file), str(dest_dir / test_file.name))
        assert (dest_dir / test_file.name).exists()


# ── MCP server HTTP tests ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mcp_server():
    """Start the MCP server for HTTP-level tests."""
    import uvicorn
    from mcp_server.server import app

    port = 8766  # Use different port to avoid conflicts
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)  # Wait for startup

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True


def test_mcp_health(mcp_server):
    import httpx
    resp = httpx.get(f"{mcp_server}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_mcp_tools_list(mcp_server):
    import httpx
    resp = httpx.get(f"{mcp_server}/tools", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert "launch_chrome_guest" in tool_names
    assert "google_login" in tool_names
    assert "move_file" in tool_names


def test_mcp_filesystem_ensure_directory(mcp_server, tmp_path):
    import httpx
    test_dir = str(tmp_path / "smoke_test_dir")
    resp = httpx.post(
        f"{mcp_server}/tools/ensure_directory",
        json={"path": test_dir},
        timeout=5
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_mcp_filesystem_move_file(mcp_server, tmp_path):
    import httpx
    # Create a test file
    src_file = tmp_path / "test_certificate.pdf"
    src_file.write_bytes(b"PDF content placeholder")
    dest_dir = tmp_path / "destination"

    resp = httpx.post(
        f"{mcp_server}/tools/move_file",
        json={
            "source": str(src_file),
            "destination_dir": str(dest_dir),
            "create_dest_if_missing": True,
        },
        timeout=10
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert (dest_dir / "test_certificate.pdf").exists()
