---
name: Backend logic review
overview: "A verified map of the Python/FastAPI backend: entrypoint, HTTP/API surface, chat and scenario pipelines, modules per training mode, persistence, and a few concrete logic/data gaps worth fixing later."
todos:
  - id: optional-fix-session-context
    content: "If multi-mode per session matters: change session_context PK or query to (session_id, mode_key) and update upsert/get paths."
    status: pending
  - id: optional-fix-files-pipeline
    content: Fix save_session_file call in rag.py; populate get_session_detail files from list_session_files.
    status: pending
  - id: optional-streaming
    content: "If true streaming is required: refactor run_chat/model client to async generator instead of word-split SSE after full completion."
    status: pending
isProject: false
---

# Backend logic re-check (verified)

## Entry and infrastructure

- **[`app.py`](d:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/app.py)** — `FastAPI` app, permissive CORS (`allow_origins=["*"]`), `SessionMiddleware` with a hardcoded secret, static mount, `init_db()` on startup, single router include from [`ui/routes.py`](d:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/routes.py).
- **Auth / roles** — Cookie session via Starlette ([`utils/security.py`](d:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/utils/security.py)): `require_user`, `require_manager` (roles `Sales Manager`, `HR`). [`/auth/start`](d:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/routes.py) upserts user in DB then sets session.

## HTTP layer (all backend behavior exposed here)

[`ui/routes.py`](d:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/routes.py) is the controller: HTML pages plus JSON/SSE APIs.

| Endpoint | Backend behavior |
|-------