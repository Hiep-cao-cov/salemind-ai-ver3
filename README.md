# Covestro Strategy Lab Enterprise v2

An enterprise-style negotiation training platform built with FastAPI + Jinja, focused on Module 2.

## Overview

The application supports multiple user roles, multiple negotiation practice modes, SQLite session persistence, and cloud model integrations (OpenAI / AWS Bedrock) for context-aware responses.

## What's New in v2

- Mode 1 (Sandbox) supports 4 scenario sources:
  - scenario library file
  - direct paste
  - upload file
  - AI-generated scenario
- Mode 1 includes an AI vs AI negotiation workflow for 8-10 turns.
- Modes 1, 2, and 3 display a model-generated scenario summary above the main chat area.
- Mode 2 allows file upload or direct case-material paste in the composer.
- Mode 3 loads scenarios from file and shows a negotiation summary before the drill.
- The left sidebar now shows history for the current mode only.

## Key Features

- Multi-user onboarding with `Name` / `CWID` / `Role`.
- Module 2 landing page with 4 mode cards.
- Mode-specific Python files: Sandbox, Real Case, Reps, and Mentor.
- Manager dashboard for usage analytics.
- Session persistence with SQLite.
- Message persistence split by module and mode.
- Context injection for uploaded scenario files (without embeddings).
- Clean workspace UI with streaming responses, typing animation, and progress bar.
- OpenAI and Bedrock support only.

## Local Setup and Run

### 1) Create environment and install dependencies

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

### 2) Run the application
```bash
uvicorn app:app --reload
```

Open your browser at: `http://127.0.0.1:8000`

## Cloud Model Configuration

### OpenAI
```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
```

### Bedrock
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-southeast-1
export BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

If neither provider is configured, the app uses a deterministic fallback so it remains runnable.

## Roles

- Sales Manager
- Marketing
- Sales Distributor
- HR

`Sales Manager` and `HR` can access the manager dashboard.

## Operational Notes

- Auto is available only in Sandbox and triggers the AI vs AI simulation workflow.
- Real Case requires uploaded or pasted case context before negotiation chat is grounded.
- No local models, no embeddings, and no LangGraph.
- Startup is lightweight; model clients initialize lazily on first use.

## Repository

- Source: [salemind-ai-ver3](https://github.com/Hiep-cao-cov/salemind-ai-ver3.git)
