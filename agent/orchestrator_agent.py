"""
Orchestrator Agent — Root Google ADK agent that coordinates all sub-agents.
Uses SequentialAgent workflow to execute tasks in order with retry logic.
"""
import asyncio
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool, agent_tool
import httpx

from agent.browser_agent import browser_agent
from agent.auth_agent import auth_agent
from agent.drive_agent import drive_agent
from agent.filesystem_agent import filesystem_agent
from config import settings
from utils.logger import get_logger
from utils.state_manager import state_manager, LoginStatus, DownloadStatus

log = get_logger("Orchestrator")
BASE_URL = settings.mcp_base_url


# ── Utility tools for the orchestrator ──────────────────────────────────────

async def get_current_status() -> dict:
    """Get the current execution state of the RPA workflow."""
    return state_manager.to_dict()


async def update_state(field: str, value: str) -> dict:
    """
    Update a state field to track workflow progress.

    Args:
        field: State field name (e.g. 'login_status', 'download_status')
        value: New value for the field
    """
    state_manager.update(**{field: value})
    return {"updated": field, "value": value}


async def log_step(step_name: str, status: str, detail: str = "") -> dict:
    """
    Log a workflow step with its status.

    Args:
        step_name: Name of the step (e.g. 'Browser Launch', 'Google Login')
        status: 'started', 'completed', 'failed'
        detail: Optional additional information
    """
    msg = f"[{step_name}] {status.upper()}"
    if detail:
        msg += f" — {detail}"
    if status == "failed":
        log.error(msg)
    elif status == "completed":
        log.success(msg)
    else:
        log.info(msg)
    return {"logged": True, "step": step_name, "status": status}


async def check_mcp_server() -> dict:
    """Verify that the MCP server is reachable."""
    import os
    if os.getenv("MOCK_MCP") == "true":
        return {"reachable": True, "response": {"status": "ok", "mock": True}}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/health")
            return {"reachable": True, "response": resp.json()}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


# ── Sequential workflow agent ─────────────────────────────────────────────────

# The sequential agent runs sub-agents one after the other in order
workflow_agent = SequentialAgent(
    name="RPAWorkflow",
    description="Sequential workflow: Browser → Auth → Drive Navigation → File System",
    sub_agents=[
        browser_agent,
        auth_agent,
        drive_agent,
        filesystem_agent,
    ],
)


# ── Root orchestrator agent ──────────────────────────────────────────────────

orchestrator_agent = LlmAgent(
    name="OrchestratorAgent",
    model="gemini-2.0-flash",
    description=(
        "Root orchestrator that coordinates the full RPA workflow: "
        "browser launch → Google login → Drive navigation → file download → file move."
    ),
    instruction=f"""You are the master orchestrator for a Google Drive RPA automation system.

## OVERALL GOAL
Download '{settings.target_file_name}' from Google Drive (inside 'My Drive > {settings.target_folder}')
and move it from '{settings.download_dir}' to '{settings.destination_dir}'.

## WORKFLOW EXECUTION STEPS

### Step 1: Pre-flight Check
- Call check_mcp_server() to verify MCP server is running
- Call log_step('Pre-flight', 'started')
- If server unreachable, log failure and stop

### Step 2: Delegate to BrowserAutomationAgent
- Instruct it to: "Launch Chrome in guest mode, then navigate to https://google.com"
- Log step start and completion
- On failure: retry up to {settings.max_retries} times

### Step 3: Delegate to AuthenticationAgent
- Instruct it to: "Log in to Google using the configured credentials"
- Handle 2FA if mentioned in response (it waits automatically)
- Log step start and completion
- On failure: report error and stop

### Step 4: Delegate to DriveNavigationAgent
- Instruct it to: "Navigate to Google Drive, open My Drive > {settings.target_folder}, and download {settings.target_file_name}"
- Log step start and completion
- On failure: retry once, then report error

### Step 5: Delegate to FileSystemAgent
- Instruct it to: "Watch for the downloaded file and move it to {settings.destination_dir}"
- Log step start and completion
- Verify final file location

### Step 6: Final Report
- Log overall success or failure
- Report: which file was moved, final path, any errors encountered

## ERROR HANDLING
- Network timeout → retry the failed step (max {settings.max_retries} times)
- Wrong password / auth failure → stop and report to user
- File not found in Drive → stop and report folder contents
- Download timeout → check if already downloaded, then report

## IMPORTANT
- Keep the user informed about each step through log_step calls
- Never expose the actual password in logs — just say "credentials provided"
- Be patient with downloads — allow up to {settings.download_timeout} seconds
""",
    tools=[
        FunctionTool(check_mcp_server),
        FunctionTool(get_current_status),
        FunctionTool(update_state),
        FunctionTool(log_step),
        agent_tool.AgentTool(agent=browser_agent),
        agent_tool.AgentTool(agent=auth_agent),
        agent_tool.AgentTool(agent=drive_agent),
        agent_tool.AgentTool(agent=filesystem_agent),
    ],
)

root_agent = orchestrator_agent
