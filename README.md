# Covestro Strategy Lab Enterprise v2

Enterprise negotiation training app built with FastAPI + Jinja, focused on Module 2 workflows.

## Overview

The app provides:

- Role-based login (`display_name`, `CWID`, `role`)
- Two active workspace modes:
  - `sandbox` (DEMO)
  - `real_case` (Practice)
- Scenario analysis and chat with persisted sessions/messages in SQLite
- Optional cloud model integrations (OpenAI / AWS Bedrock), with deterministic fallback when not configured

## Current Product Flow

### 1) DEMO (`/workspace/sandbox`)

- Scenario source options:
  - AI create scenario
  - Scenario library
  - Upload file
  - Paste scenario text
- Step-by-step DEMO simulation (`Start DEMO` + `Next turn`)
- Optional mentor insight per turn
- Difficulty levels: `simple`, `medium`, `hard`
- Help/Coach actions and normal negotiated chat with AI seller

### 2) Practice (`/workspace/real_case`)

- Scenario source options:
  - Scenario library
  - Paste case text
  - Upload file
- User can choose practice role (`buyer` or `seller`)
- Scenario is analyzed first, then negotiation chat continues with role-aware responses
- `Finish` action supports:
  - keep scenario + clear chat
  - full reset (clear context/files/chat metadata)

## Key Features

- FastAPI backend with Jinja templates
- Streaming chat responses (SSE)
- Scenario analysis modes:
  - `no_llm`
  - `local_model`
  - `cloud_model`
- Manager analytics dashboard (`/manager`) for manager roles
- SQLite persistence for users, sessions, context, and messages
- Upload context extraction pipeline (no embeddings)

## Local Setup

### 1) Create virtual environment and install dependencies

#### macOS / Linux
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Run app

```bash
uvicorn app:app --reload
```

Open: `http://127.0.0.1:8000`

## Environment Variables

### OpenAI

#### macOS / Linux
```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
```

#### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your_key"
$env:OPENAI_MODEL="gpt-4o-mini"
```

### AWS Bedrock

#### macOS / Linux
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-southeast-1
export BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

#### Windows (PowerShell)
```powershell
$env:AWS_ACCESS_KEY_ID="your_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret"
$env:AWS_DEFAULT_REGION="ap-southeast-1"
$env:BEDROCK_MODEL_ID="anthropic.claude-3-haiku-20240307-v1:0"
```

If neither provider is configured, the app still runs using fallback behavior.

## Roles

- Sales Manager
- Marketing
- Sales Distributor
- HR

`Sales Manager` and `HR` can access manager endpoints/dashboard.

## Notes

- Active frontend script is `ui/static/js/app.js`.
- Step-by-step DEMO endpoint is `/api/sandbox/simulate-step`.
- Model clients initialize lazily at runtime.

## Repository

- Source: [salemind-ai-ver3](https://github.com/Hiep-cao-cov/salemind-ai-ver3.git)
