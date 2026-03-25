"""
Main entry point — starts the MCP server in a background thread and runs
the ADK orchestrator agent to execute the full RPA workflow.
"""
import asyncio
import sys
import os
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import google.generativeai as genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from config import settings
from utils.logger import get_logger
from utils.state_manager import state_manager

log = get_logger("Main")


# ── Configure Gemini API key ─────────────────────────────────────────────────

os.environ["GOOGLE_API_KEY"] = settings.google_api_key
genai.configure(api_key=settings.google_api_key)


# ── MCP Server startup ───────────────────────────────────────────────────────

def start_mcp_server():
    """Start the FastAPI MCP server in a background thread."""
    from mcp_server.server import run_server
    run_server(host=settings.mcp_server_host, port=settings.mcp_server_port)


def wait_for_server(host: str, port: int, timeout: int = 30) -> bool:
    """Wait until the MCP server is accepting connections."""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://{host}:{port}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ── Main async workflow ──────────────────────────────────────────────────────

async def run_rpa_workflow():
    """
    Execute the full RPA automation workflow via the orchestrator agent.
    Returns the final result text.
    """
    from agent.orchestrator_agent import orchestrator_agent

    log.info("=" * 60)
    log.info("  Google Drive RPA — Multi-Agent System")
    log.info("  Powered by Google ADK + MCP")
    log.info("=" * 60)

    # Reset state for fresh run
    state_manager.reset()

    # Create ADK session service and runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=orchestrator_agent,
        app_name="GoogleDriveRPA",
        session_service=session_service,
    )

    # Create a session
    session = await session_service.create_session(
        app_name="GoogleDriveRPA",
        user_id="rpa_user",
        session_id="rpa_session_001",
        state=state_manager.to_dict(),
    )

    # Build the initial user message
    task_message = f"""
    Execute the complete Google Drive RPA workflow:

    1. Launch Chrome browser in guest mode
    2. Search Google for "Google Drive" and navigate to https://drive.google.com/
    3. Log in with: Email={settings.google_email}
       (Password is configured — use the AuthenticationAgent)
    4. Navigate: My Drive → {settings.target_folder}
    5. Download: {settings.target_file_name} (PDF)
    6. Move downloaded file from: {settings.download_dir}
       To: {settings.destination_dir}

    Please proceed step by step and report progress.
    """

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=task_message)]
    )

    log.info("Starting orchestrator agent...")
    log.info(f"Target: {settings.target_file_name}")
    log.info(f"Destination: {settings.destination_dir}")

    # Run the agent
    final_response = ""
    async for event in runner.run_async(
        user_id="rpa_user",
        session_id="rpa_session_001",
        new_message=user_message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text
                log.info(f"\n{'='*60}\nFINAL RESULT:\n{final_response}\n{'='*60}")

    return final_response


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    log.info("Starting MCP server in background...")

    # Start MCP server in daemon thread
    server_thread = threading.Thread(target=start_mcp_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    log.info(f"Waiting for MCP server at {settings.mcp_server_host}:{settings.mcp_server_port}...")
    if not wait_for_server(settings.mcp_server_host, settings.mcp_server_port, timeout=30):
        log.error("MCP server failed to start within 30 seconds!")
        sys.exit(1)

    log.info("✓ MCP server is ready")

    # Run the workflow
    try:
        result = asyncio.run(run_rpa_workflow())
        log.info("Workflow completed successfully!")
        return result
    except KeyboardInterrupt:
        log.info("Workflow interrupted by user.")
    except Exception as e:
        log.error(f"Workflow failed: {e}")
        raise


if __name__ == "__main__":
    main()
