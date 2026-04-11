---
name: Codebase Orientation
overview: Establish a shared understanding of the app architecture, request flow, and key extension points before making code changes.
todos:
  - id: trace-request-lifecycle
    content: Map end-to-end request flow across routes, core services, and DB writes.
    status: completed
  - id: catalog-config-surface
    content: List env/config dependencies and where each is consumed.
    status: completed
  - id: identify-risk-hotspots
    content: Highlight highest-impact maintainability/security risks with recommended next actions.
    status: completed
isProject: false
---

# Codebase Orientation Plan

## What I found
- App is a FastAPI + Jinja2 web app bootstrapped in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/app.py`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/app.py), with CORS, cookie sessions, static mounting, router registration, and DB init on startup.
- Route/controller layer is concentrated in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/routes.py`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/routes.py), mixing page routes and APIs (`/api/scenario/prepare`, `/api/chat/stream`, `/api/sandbox/simulate`, analytics/session endpoints).
- Core orchestration sits in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/core`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/core) (chat engine, model client, RAG/file extraction, prompt/state logic).
- Business-mode logic is split under [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/modules/module2`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/modules/module2) (`sandbox`, `real_case`, `reps`, `mentor`) plus manager analytics in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/modules/manager`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/modules/manager).
- Data layer is SQLite via function-based repository helpers in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/utils/db.py`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/utils/db.py); no migration framework detected.
- Frontend is server-rendered templates in [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/templates`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/templates) with one main client script [`D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/static/js/app.js`](D:/NEW_HOME_PROJECT/SALEMIND-WEB/enterprise-my-ai-sales-app-v2/ui/static/js/app.js) handling API calls, SSE parsing, and workspace state.

## Architecture map
```mermaid
flowchart TD
  Browser[BrowserUI] --> Routes[ui_routes.py]
  Routes --> Templates[ui_templates]
  Browser --> JS[ui_static_js_app.js]
  JS --> ApiScenario[/api/scenario/prepare]
  JS --> ApiChat[/api/chat/stream]
  JS --> ApiSim[/api/sandbox/simulate]
  ApiScenario --> CoreRag[core_rag.py]
  ApiChat --> ChatEngine[core_chat_engine.py]
  ApiSim --> SandboxModule[module2_sandbox.py]
  ChatEngine --> ModelClient[core_model_client.py]
  Routes --> Security[utils_security.py]
  Routes --> DB[utils_db.py]
  CoreRag --> DB
  ChatEngine --> DB
```

## Next discovery pass (after approval)
- Trace one full happy-path request lifecycle (`/auth/start` -> `/workspace/{mode}` -> `/api/chat/stream`) with exact function call chain.
- Document config/env surface (model providers, session secrets, DB paths) from runtime files and `README.md`.
- Identify top risk/tech-debt hotspots (security defaults, coupling points, data consistency) and propose prioritized remediation options.