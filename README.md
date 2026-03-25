# DriveBot — Autonomous Google Drive RPA System

> *Powered by Google ADK · MCP · Playwright · Gemini 2.0*

An enterprise-grade, multi-agent Robotic Process Automation (RPA) system that automates end-to-end Google Drive workflows — from browser launch and authentication to file navigation, download, and local file management — entirely without human interaction.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Agent System](#agent-system)
- [MCP Server & Tools](#mcp-server--tools)
- [Evaluation](#evaluation)
- [Testing](#testing)
- [Error Handling & Retry Logic](#error-handling--retry-logic)
- [Logging](#logging)

---

## Overview

This system uses **Google's Agent Development Kit (ADK)** to orchestrate a pipeline of specialized AI agents, each responsible for a distinct phase of the RPA workflow:

1. **Launch** Chrome in guest mode (no stored sessions or cookies)
2. **Authenticate** into a Google account (with automatic 2FA detection)
3. **Navigate** Google Drive to a target folder
4. **Download** a specific file (PDF)
5. **Move** the downloaded file to a configured local destination

The agents communicate through a local **MCP (Model Context Protocol) server** — a FastAPI application exposing browser, auth, drive, and filesystem operations as HTTP tool endpoints.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OrchestratorAgent                       │
│              (Gemini 2.0 Flash · Google ADK)                 │
└──────────┬──────────┬──────────┬──────────┬─────────────────┘
           │          │          │          │
    ┌──────▼──┐ ┌─────▼───┐ ┌───▼──────┐ ┌▼───────────────┐
    │ Browser │ │  Auth   │ │  Drive   │ │   Filesystem   │
    │  Agent  │ │  Agent  │ │  Agent   │ │     Agent      │
    └──────┬──┘ └─────┬───┘ └───┬──────┘ └┬───────────────┘
           │          │          │          │
           └──────────┴──────────┴──────────┘
                              │
                   ┌──────────▼──────────┐
                   │    MCP Server       │
                   │  (FastAPI · HTTP)   │
                   ├─────────────────────┤
                   │  /tools/browser_*   │
                   │  /tools/auth_*      │
                   │  /tools/drive_*     │
                   │  /tools/filesystem_*│
                   └──────────┬──────────┘
                              │
                   ┌──────────▼──────────┐
                   │  Playwright Browser │
                   │  (Chromium + Stealth│
                   └─────────────────────┘
```

The orchestrator delegates tasks to sub-agents via `AgentTool`. Each sub-agent wraps MCP tool calls through typed Python functions, which are surfaced to Gemini as `FunctionTool` definitions.

---

## Project Structure

```
project-root/
│
├── main.py                         # Entry point: starts MCP server + runs workflow
├── run_eval.py                     # ADK evaluation runner
├── requirements.txt
│
├── agent/
│   ├── __init__.py
│   ├── orchestrator_agent.py       # Root LlmAgent coordinating the workflow
│   ├── browser_agent.py            # Chrome launch + page interaction
│   ├── auth_agent.py               # Google login + 2FA handling
│   ├── drive_agent.py              # Drive navigation + file download
│   └── filesystem_agent.py         # File watching + move to destination
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                   # FastAPI app, tool listing, shared browser state
│   ├── browser_tools.py            # Playwright browser tool endpoints
│   ├── auth_tools.py               # Google auth tool endpoints
│   ├── drive_tools.py              # Drive navigation + download endpoints
│   └── filesystem_tools.py         # Directory + file move endpoints
│
├── utils/
│   ├── logger.py                   # Loguru structured logger (console + file)
│   ├── state_manager.py            # Thread-safe singleton execution state
│   └── error_handler.py            # Custom exceptions + retry decorator
│
├── config.py                       # Pydantic settings (loaded from .env)
│
├── tests/
│   └── test_smoke.py               # Import, server, and integration smoke tests
│
└── evals/
    └── rpa_eval_v2.evalset.json    # ADK eval set definition
```

---

## Prerequisites

- Python **3.11+**
- Node.js (optional, for docx tooling)
- **Google Chrome** installed on the host machine
- A Google account with access to the target Drive folder
- A valid **Google Gemini API key** (for ADK agent inference)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/drivebot-rpa.git
cd drivebot-rpa

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```dotenv
# Google Account Credentials
GOOGLE_EMAIL=your.email@gmail.com
GOOGLE_PASSWORD=your_password

# Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key

# File Paths
DOWNLOAD_DIR=C:\Users\YourName\Downloads
DESTINATION_DIR=D:\test
TARGET_FOLDER=Coursera Certificates
TARGET_FILE_NAME=NVIDIA Fundamentals of Deep Learning

# MCP Server
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8765

# Workflow Settings
MAX_RETRIES=3
DOWNLOAD_TIMEOUT=120
```

> **Security note:** Never commit `.env` to version control. Add it to `.gitignore`. Credentials are read at runtime via `pydantic-settings` and are never logged.

---

## Usage

### Run the full RPA workflow

```bash
python main.py
```

This will:
1. Start the MCP server in a background thread on `localhost:8765`
2. Wait for the server to be healthy
3. Invoke the orchestrator agent with the full task description
4. Stream agent progress to the console and `logs/rpa.log`

### Run in mock mode (no real browser)

```bash
MOCK_MCP=true python main.py
```

When `MOCK_MCP=true`, all MCP tool calls return a mock success response. Useful for testing agent logic without a live browser or Google session.

---

## Agent System

All agents are built with `google.adk.agents.LlmAgent` using **Gemini 2.0 Flash** as the inference model.

### OrchestratorAgent

The root agent. Coordinates the full pipeline using `AgentTool` wrappers to delegate to sub-agents. Handles retry logic, step logging, and state updates via `FunctionTool` utilities.

### BrowserAutomationAgent

Wraps all Playwright browser operations: launching Chrome in guest mode, navigating URLs, clicking elements, typing text, and taking screenshots.

### AuthenticationAgent

Handles the complete Google login flow: entering email, entering password, detecting 2FA challenges, and waiting for manual 2FA completion via polling.

### DriveNavigationAgent

Navigates Google Drive: clicks "My Drive", opens a named subfolder, locates a file by name pattern, triggers a right-click download, and monitors completion.

### FileSystemAgent

Ensures the destination directory exists, watches the download directory for the completed file using `watchdog`, and moves it to the configured destination.

---

## MCP Server & Tools

The MCP server runs as a local FastAPI application and exposes 20 tools across 4 categories:

| Category | Tools |
|---|---|
| **Browser** | `launch_chrome_guest`, `navigate_to`, `click_element`, `type_text`, `wait_for_element`, `take_screenshot`, `get_page_url`, `get_page_content`, `press_key` |
| **Auth** | `google_login`, `check_login_status`, `handle_2fa_wait` |
| **Drive** | `click_my_drive`, `open_drive_folder`, `find_and_download_file`, `wait_for_download` |
| **Filesystem** | `ensure_directory`, `move_file`, `watch_for_file`, `list_directory` |

Tool discovery is available at `GET /tools`. Health check at `GET /health`.

---

## Evaluation

The project uses **Google ADK's `AgentEvaluator`** with rubric-based metrics to assess agent performance against a reference trajectory.

```bash
python run_eval.py
```

Two prebuilt metrics are evaluated:

- `rubric_based_final_response_quality_v1` — Did the agent achieve the stated goal?
- `rubric_based_tool_use_quality_v1` — Did the agent use tools in the correct sequence?

Eval cases are defined in `evals/rpa_eval_v2.evalset.json` using a `conversation_scenario` with a starting prompt and a conversation plan describing expected agent behaviour.

**Latest results (2026-03-06):** Both metrics passed with a threshold of 0.8.

---

## Testing

Run the smoke test suite to verify imports, configuration, server startup, and basic tool functionality:

```bash
pytest tests/test_smoke.py -v
```

The smoke tests cover:

- Configuration loading and validation
- All module imports (agents, tools, server, utils)
- Retry decorator (sync and async)
- State manager singleton and update logic
- MCP server HTTP endpoints (`/health`, `/tools`, `/tools/ensure_directory`, `/tools/move_file`)
- Filesystem operations using `tempfile` (no real paths required)

> The MCP server is started on port `8766` during tests to avoid conflicts with a running instance on `8765`.

---

## Error Handling & Retry Logic

Custom exceptions are defined in `utils/error_handler.py` and map to specific failure modes:

| Exception | Cause |
|---|---|
| `BrowserError` | Chrome failed to launch or navigate |
| `AuthenticationError` | Wrong credentials or CAPTCHA blocked |
| `TwoFactorRequired` | Google 2FA challenge detected |
| `DriveNavigationError` | Folder or file not found in Drive |
| `DownloadError` | File did not complete downloading within timeout |
| `FileSystemError` | File move or directory creation failed |
| `MCPConnectionError` | MCP server unreachable |

The `@retry` decorator supports both sync and async functions and accepts configurable `max_attempts`, `delay`, and exception tuple parameters.

---

## Logging

Logging is powered by **Loguru** with two sinks:

- **Console** — coloured output at `INFO` level, formatted with agent name and timestamp
- **File** — `logs/rpa.log` at `DEBUG` level, with 10 MB rotation and 7-day retention

Each module binds a named logger via `get_logger("AgentName")`, making log output easy to filter by component.

```
11:50:17 | SUCCESS  | Orchestrator         | [Browser Launch] COMPLETED
11:50:35 | SUCCESS  | Orchestrator         | [Google Login] COMPLETED
11:51:03 | SUCCESS  | Orchestrator         | [Drive Navigation] COMPLETED
11:51:33 | SUCCESS  | Orchestrator         | [File Move] COMPLETED
```

Screenshots on error are saved to `logs/screenshots/`.

---

## License

MIT License. See `LICENSE` for details.
