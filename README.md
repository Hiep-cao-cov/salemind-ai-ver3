# Covestro Strategy Lab Enterprise v2

A FastAPI + Jinja enterprise-style negotiation training platform focused on Module 2.

## What changed in v2
- Mode 1 Sandbox supports four scenario sources:
  - scenario library file
  - direct paste
  - file upload
  - AI-generated scenario
- Mode 1 then runs AI vs AI negotiation for 8–10 turns
- Modes 1, 2, and 3 display model-generated scenario summaries above the main chat area
- Mode 2 can upload files or paste case material directly in the composer area
- Mode 3 loads scenarios from the scenario file and displays their negotiation summary before the drill
- The left sidebar now shows history for the **current mode only**

## Features
- Multi-user onboarding with Name/CWID/Role
- Module 2 landing and 4 mode cards
- Separate Python files for Sandbox, Real Case, Reps, and Mentor
- Manager dashboard for usage analytics
- Session persistence in SQLite
- Message persistence split by module and mode
- Context injection for uploaded scenario files without embeddings
- Clean workspace UI with streaming responses, typing animation, and progress bar
- OpenAI and Bedrock support only

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```
https://github.com/Hiep-cao-cov/salemind-ai-ver3.git

Open `http://127.0.0.1:8000`

## Cloud model setup
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

If neither provider is configured, the app uses a deterministic commercial fallback so it remains runnable.

## Roles
- Sales Manager
- Marketing
- Sales Distributor
- HR

Sales Manager and HR can access the manager dashboard.

## Notes
- Auto is available only in Sandbox and it triggers the AI vs AI simulation workflow
- Real Case requires uploaded or pasted case context before negotiation chat becomes grounded
- No local models, no embeddings, no LangGraph
- Startup is lightweight; model clients initialize lazily when first used
