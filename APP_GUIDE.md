# Covestro Strategy Lab Enterprise - Application Guide

This guide explains product logic and implementation details so you can reuse this design to build a similar negotiation training app.

Use `README.md` for setup and run commands. Use this file for architecture and strategy behavior.

---

## 1) Product objective

Build a practical negotiation simulator with two learning modes:

- `sandbox` (DEMO): step-by-step AI simulation
- `real_case` (Practice): role-play against AI with mentor coaching

Core outcomes:

- Train users to negotiate with structure
- Make AI behavior controllable via difficulty and role
- Provide mentor coaching that is tactical, concrete, and easy to act on

---

## 2) Current system blueprint

Main stack:

- Backend: FastAPI (`app.py`, `ui/routes.py`)
- Frontend: Jinja + Vanilla JS (`ui/templates/workspace.html`, `ui/static/js/app.js`)
- Database: SQLite (`utils/db.py`)
- AI layer: `core/model_client.py`, `modules/module2/sandbox.py`, `modules/module2/real_case.py`

High-level flow:

1. User opens workspace mode
2. User prepares scenario (library/upload/paste/AI generated)
3. App analyzes scenario context
4. User negotiates with AI
5. Mentor returns tactical coaching (Practice, optional)
6. Session history persists for replay and learning

---

## 3) Session and history behavior (final UX)

### Mode separation

- DEMO history is shown only in DEMO sidebar
- Practice history is shown only in Practice sidebar
- Titles include mode tag, for example:
  - `[DEMO] ...`
  - `[PRACTICE] ...`

### New session behavior

- Clicking `+` creates an immediate temporary draft history item
- Draft is marked with `is_draft=1`
- If user leaves/switches mode without Analyze and without chat, draft is auto-discarded
- Once user starts Analyze, draft becomes normal saved session (`is_draft=0`)

### History row metadata chips

Each row shows:

- Difficulty (`Simple/Medium/Hard`)
- Mentor (`On/Off`)
- State (`Draft/Analyzed`)

This makes history list scannable and actionable.

---

## 4) Negotiation strategy design (reusable model)

A strong negotiation-training app should force this order:

1. **Situation understanding** (scenario analysis)
2. **Positioning** (role context, value anchors)
3. **Execution** (turn-by-turn strategy)
4. **Coaching loop** (mentor feedback)

This project follows that model:

- Step 1 + Step 2 provide context and tactical baseline
- Step 3 runs negotiation turns
- Mentor explains why an AI turn matters and what to do next

---

## 5) Difficulty levels and expected AI behavior

Difficulty is not just wording style. It should change negotiation pressure.

### `simple`

- AI is cooperative and explicit
- Fewer hidden constraints
- Easier to identify needs and propose options
- Good for onboarding

### `medium`

- Balanced challenge
- Some objections and pushback
- Requires value framing plus clarification questions
- Default training mode

### `hard`

- Higher resistance and ambiguity
- Stronger commercial pressure
- More strategic testing of concessions and confidence
- Requires disciplined trade logic and tighter framing

Implementation note:

- Difficulty is passed from UI to backend per turn
- It is also saved at session level for history replay and continuity

---

## 6) Mentor role and output strategy

In Practice mode, mentor is a tactical coach, not another negotiator.

Mentor should answer:

- What just happened?
- Why does it matter strategically?
- What exact next responses should user try?

### Required mentor output structure

Mentor output is normalized into three sections:

1. **Summary**
2. **Tactical analysis**
3. **Suggested responses strategies**

UI formatting rules:

- Section labels are highlighted/bold
- Suggested responses are rendered as bullets
- Up to 4 bullet sentences for readability
- Leading dash characters are removed automatically

This formatting is applied to:

- New live mentor messages
- Recalled mentor messages in history

---

## 7) What affects mentor output quality

Mentor output quality depends on these inputs:

- Scenario analysis quality (`summary`, key points, negotiation points)
- Recent dialogue context quality
- Practice role (`buyer` vs `seller`)
- Difficulty level
- Mentor toggle (`on/off`)

Practical guideline:

- If mentor output is generic, improve scenario analysis richness and recent dialogue payload first.

---

## 8) Real Case flow (reference implementation)

1. User selects role
2. User analyzes case
3. User starts negotiation
4. AI counterparty responds turn by turn
5. Mentor analyzes AI turn and returns structured coaching
6. User applies suggested strategy in next turn

This loop creates fast experiential learning.

---

## 9) Key APIs and ownership rules

Main APIs:

- `POST /api/scenario/prepare`
- `POST /api/chat/stream`
- `POST /api/session/practice-role`
- `POST /api/session/ui-prefs`
- `POST /api/session/title`
- `POST /api/session/discard-draft`
- `POST /api/session/delete`
- `POST /api/session/finish-negotiation`

Security rule:

- Every API that accepts `session_id` validates session ownership against current user.

---

## 10) Reuse checklist for building similar apps

If you want to clone this product pattern:

- Keep mode-specific history separation
- Add draft lifecycle for clean UX
- Persist user coaching preferences per session
- Make mentor output structured and scannable
- Tie difficulty to behavior, not only style
- Save analysis and conversation together for replay
- Use inline rename and metadata chips for session management

---

## 11) Where to modify by concern

- Route/API behavior: `ui/routes.py`
- Persistence and schema: `utils/db.py`
- Practice AI logic and mentor fallback: `modules/module2/real_case.py`
- DEMO turn logic: `modules/module2/sandbox.py`
- Mentor rendering and formatting: `ui/static/js/app.js`
- Workspace layout and sidebar: `ui/templates/workspace.html`
- UX style: `ui/static/css/workspace-v2.css`

---

This guide is intentionally implementation-focused so product, engineering, and AI prompt teams can align quickly when creating similar negotiation simulators.
