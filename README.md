# Covestro Strategy Lab Enterprise v2

Enterprise negotiation training app built with FastAPI + Jinja, focused on Module 2 workflows.

## What the app does

- Role-based login (`display_name`, `CWID`, `role`)
- Two active workspace modes:
  - `sandbox` (DEMO)
  - `real_case` (Practice)
- Scenario analysis + negotiation chat with session history in SQLite
- Mentor support with structured coaching output in Practice mode
- Optional cloud model integrations (OpenAI / AWS Bedrock), with fallback behavior

## Current UX flow

### DEMO mode (`/workspace/sandbox`)

- User can start from AI scenario, library, upload, or pasted text
- `Analyze Scenario` prepares context first
- Negotiation runs step-by-step (`Start DEMO`, `Next turn`)
- Difficulty (`simple`, `medium`, `hard`) and Mentor (`on/off`) affect output

### Practice mode (`/workspace/real_case`)

- User can start from library, upload, or pasted case text
- User chooses role (`buyer` or `seller`)
- Negotiation starts after analysis
- Mentor output is formatted into:
  - **Summary**
  - **Tactical analysis**
  - **Suggested responses strategies** (up to 4 bullet sentences)

## History and session behavior

- History is separated by mode:
  - DEMO history appears only in DEMO sidebar
  - Practice history appears only in Practice sidebar
- Session titles include mode tag (for example `[DEMO] ...`, `[PRACTICE] ...`)
- `+` in sidebar creates a temporary draft history row immediately
- If draft is not analyzed and user leaves/switches mode, draft is auto-discarded
- History row shows useful chips:
  - difficulty
  - mentor on/off
  - analyzed/draft status
- Session title can be renamed inline in sidebar

## Local setup

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

## Environment variables

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

If neither provider is configured, the app still runs with fallback behavior.

## Roles

- Sales Manager
- Marketing
- Sales Distributor
- HR

`Sales Manager` and `HR` can access manager dashboard (`/manager`).

## Notes

- Active frontend script: `ui/static/js/app.js`
- DEMO step endpoint: `/api/sandbox/simulate-step`
- Workspace route and APIs: `ui/routes.py`
- SQLite helpers: `utils/db.py`

## Repository

- Source: [salemind-ai-ver3](https://github.com/Hiep-cao-cov/salemind-ai-ver3.git)
