import json
from typing import Dict, List, Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from core.chat_engine import (
    prepare_mode_context_v2,
    run_chat,
    run_sandbox_simulation,
    run_sandbox_simulation_step,
)
from core.agents.real_case_user_audit import audit_real_case_user_message
from core.model_client import get_active_model_info, scenario_analyzer_display_line
from core.scenario_store import get_scenario_by_id, load_scenarios
from modules.manager.dashboard import load_dashboard_data


from utils.db import (
    add_message,
    add_messages,
    create_session,
    delete_messages_for_session_mode,
    delete_session_context_row,
    delete_session_files_meta,
    get_manager_analytics,
    get_session,
    get_session_context,
    get_session_detail,
    list_recent_sessions_for_user,
    update_session_mode,
    update_session_practice_role,
    upsert_session_context,
    upsert_user,
)
from utils.security import clear_user_session, get_current_user, require_manager, require_user, set_user_session
from core.rag import save_uploaded_context

router = APIRouter()


templates = Jinja2Templates(directory="ui/templates")

JOB_ROLES = ["Sales Manager", "Marketing", "Sales Distributor", "HR"]
DEFAULT_MODE = "sandbox"
MODE_LABELS: Dict[str, str] = {
    "sandbox": "DEMO",
    "real_case": "PRACTICE",
}


def _base_context(request: Request) -> Dict[str, object]:
    return {
        "request": request,
        "current_user": get_current_user(request),
        "job_roles": JOB_ROLES,
    }


def _messages_with_parsed_audit(detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in detail.get("messages") or []:
        row = dict(m)
        try:
            row["audit"] = json.loads(row.get("audit_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            row["audit"] = {}
        out.append(row)
    return out


def _serialize_context(mode_context: Dict[str, object] | None) -> Dict[str, object] | None:
    if not mode_context:
        return None

    analysis = mode_context.get("analysis") or {}
    return {
        "source_type": mode_context.get("source_type", ""),
        "source_name": mode_context.get("source_name", ""),
        "title": analysis.get("title", ""),
        "summary": analysis.get("summary", ""),
        "stakeholders": analysis.get("stakeholders", {"buyer": "", "seller": ""}),
        "pain_points": analysis.get("pain_points", []),
        "risks": analysis.get("risks", []),
        "power_dynamics": analysis.get("power_dynamics", []),
        "key_points": analysis.get("key_points", []),
        "negotiation_points": analysis.get("negotiation_points", []),
        "recommended_strategies": analysis.get("recommended_strategies", []),
        "tactical_suggestions": analysis.get("tactical_suggestions", []),
        "possible_objections": analysis.get("possible_objections", []),
        "generated_scenario": analysis.get("generated_scenario", ""),
        "raw_text": mode_context.get("raw_text", ""),
    }


def _sync_db_user(request: Request) -> Dict[str, Any]:
    """
    Ensure the cookie/session user also exists in DB.
    This prevents stale browser session vs DB mismatch after DB reset.
    """
    user = require_user(request)

    db_user = upsert_user(
        cwid=user["cwid"],
        display_name=user["display_name"],
        role=user["role"],
    )

    # Keep the current runtime user aligned with DB identity
    user["id"] = db_user["id"]
    return user


# =========================
# PAGE ROUTES
# =========================

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_base_context(request),
    )


@router.post("/auth/start")
def auth_start(
    request: Request,
    display_name: str = Form(...),
    cwid: str = Form(...),
    role: str = Form(...),
):
    user = upsert_user(
        cwid=cwid.strip(),
        display_name=display_name.strip() or cwid.strip(),
        role=role,
    )
    session_payload = {
        "id": user["id"],
        "display_name": user["display_name"],
        "cwid": user["cwid"],
        "role": user["role"],
    }
    set_user_session(request, session_payload)
    return RedirectResponse(url=f"/workspace/{DEFAULT_MODE}", status_code=303)


@router.get("/logout")
def logout(request: Request):
    clear_user_session(request)
    return RedirectResponse(url="/", status_code=303)


@router.get("/module-2", response_class=HTMLResponse)
def module2(request: Request):
    _sync_db_user(request)
    return RedirectResponse(url=f"/workspace/{DEFAULT_MODE}", status_code=303)


@router.get("/workspace/{mode}", response_class=HTMLResponse)
def workspace(request: Request, mode: str, session_id: str | None = None):
    user = _sync_db_user(request)

    normalized_mode = (mode or "").strip().lower()
    if normalized_mode not in MODE_LABELS:
        normalized_mode = DEFAULT_MODE
    mode = normalized_mode

    if session_id:
        session = get_session(session_id)
        if not session or session["user_id"] != user["id"]:
            raise HTTPException(status_code=404, detail="Session not found")
        update_session_mode(session_id, mode)
    else:
        session_id = create_session(
            user_id=user["id"],
            module_key="module_2",
            mode_key=mode,
            title=f"{MODE_LABELS[mode]} Session",
        )

    sess_row = get_session(session_id) or {}
    raw_pr = sess_row.get("practice_role")
    pr_norm = str(raw_pr or "").strip().lower()
    if pr_norm in ("buyer", "seller"):
        practice_role = pr_norm
    else:
        practice_role = "seller"
        if mode == "real_case":
            update_session_practice_role(session_id, practice_role)

    detail = get_session_detail(session_id)
    mode_context = _serialize_context(detail.get("context"))

    context = _base_context(request)
    context.update(
        {
            "mode": mode,
            "mode_label": MODE_LABELS[mode],
            "session_id": session_id,
            "messages": _messages_with_parsed_audit(detail),
            "session_files": detail["files"],
            "recent_sessions": list_recent_sessions_for_user(user["id"], mode_key=mode, limit=12),
            "scenario_library": load_scenarios(),
            "mode_context": mode_context,
            "has_context": bool(mode_context and mode_context.get("summary")),
            "model_info": get_active_model_info(),
            "practice_role": practice_role,
            "analyzer_line_no_llm": scenario_analyzer_display_line("no_llm"),
            "analyzer_line_local": scenario_analyzer_display_line("local_model"),
            "analyzer_line_cloud": scenario_analyzer_display_line("cloud_model"),
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="workspace.html",
        context=context,
    )


# =========================
# SCENARIO PREP
# =========================

@router.post("/api/scenario/prepare")
async def api_prepare_scenario(
    request: Request,
    session_id: str = Form(...),
    mode: str = Form(...),
    source_type: str = Form(...),
    analyzer_mode: str = Form("no_llm"),
    scenario_key: str = Form(""),
    content: str = Form(""),
    file: UploadFile | None = File(None),
):
    user = require_user(request)
    session = get_session(session_id)

    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    if mode not in {"sandbox", "real_case"}:
        raise HTTPException(status_code=400, detail="This mode does not support scenario preparation")

    raw_text = ""
    source_name = ""

    if source_type == "library":
        scenario = get_scenario_by_id(scenario_key)
        if not scenario:
            raise HTTPException(status_code=400, detail="Scenario not found")
        raw_text = scenario["context"]
        source_name = scenario["title"]

    elif source_type == "upload":
        if not file:
            raise HTTPException(status_code=400, detail="File is required")

        data = await file.read()
        file_result = save_uploaded_context(session_id, file.filename, data)

        raw_text = str(file_result["extracted_text"])
        source_name = str(file_result["file_name"])

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in the uploaded file")

    elif source_type == "ai":
        raw_text = content.strip()
        source_name = "AI Generated Scenario"

        analysis = prepare_mode_context_v2(
            mode=mode,
            source_type=source_type,
            source_name=source_name,
            raw_text=raw_text,
            analyzer_mode=analyzer_mode,
        )

        upsert_session_context(
            session_id,
            "module_2",
            mode,
            source_type,
            source_name,
            analysis.get("generated_scenario", "") or raw_text,
            analysis,
        )
        return JSONResponse({"ok": True, "context": analysis})

    else:
        raw_text = content.strip()
        source_name = "Direct Input"

        if not raw_text:
            raise HTTPException(status_code=400, detail="Scenario content is required")

    analysis = prepare_mode_context_v2(
        mode=mode,
        source_type=source_type,
        source_name=source_name,
        raw_text=raw_text,
        analyzer_mode=analyzer_mode,
    )

    upsert_session_context(
        session_id,
        "module_2",
        mode,
        source_type,
        source_name,
        raw_text,
        analysis,
    )

    return JSONResponse({"ok": True, "context": analysis})


# =========================
# SESSION — PRACTICE ROLE
# =========================

@router.post("/api/session/practice-role")
async def api_session_practice_role(request: Request):
    user = _sync_db_user(request)
    payload = await request.json()
    session_id = str(payload.get("session_id", "")).strip()
    role = str(payload.get("practice_role", "")).strip().lower()
    if role not in ("buyer", "seller"):
        raise HTTPException(status_code=400, detail="practice_role must be buyer or seller")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    update_session_practice_role(session_id, role)
    return JSONResponse({"ok": True})


@router.post("/api/session/finish-negotiation")
async def api_finish_negotiation(request: Request):
    user = _sync_db_user(request)
    payload = await request.json()
    session_id = str(payload.get("session_id", "")).strip()
    resolution = str(payload.get("resolution", "")).strip().lower()
    if resolution not in ("keep_scenario", "full_reset"):
        raise HTTPException(
            status_code=400,
            detail="resolution must be keep_scenario or full_reset",
        )
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    mode_key = str(session.get("mode_key") or "").strip()
    if mode_key not in ("sandbox", "real_case"):
        raise HTTPException(
            status_code=400,
            detail="Finish is only available in DEMO or Practice mode",
        )
    delete_messages_for_session_mode(session_id, "module_2", mode_key)
    if resolution == "full_reset":
        delete_session_context_row(session_id)
        delete_session_files_meta(session_id)

    return JSONResponse({"ok": True, "resolution": resolution})


# =========================
# CHAT STREAM
# =========================

@router.post("/api/chat/stream")
async def api_chat_stream(request: Request):
    user = _sync_db_user(request)
    payload = await request.json()

    session_id = str(payload.get("session_id", "")).strip()
    mode = str(payload.get("mode", "")).strip()
    action = str(payload.get("action", "chat")).strip()
    message = str(payload.get("message", "")).strip()
    action_lower = action.lower()

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")

    if mode not in MODE_LABELS:
        raise HTTPException(status_code=400, detail="Invalid mode")

    if action_lower == "start" and mode != "real_case":
        raise HTTPException(status_code=400, detail="Start action is only supported in Practice mode")

    if not message and action_lower == "chat":
        raise HTTPException(status_code=400, detail="Message is required")

    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    mode_context = get_session_context(session_id, mode)

    if action_lower == "start":
        if not mode_context:
            raise HTTPException(status_code=400, detail="Select a scenario source and click Analyze Scenario first")
        analysis_gate = mode_context.get("analysis")
        if not isinstance(analysis_gate, dict):
            analysis_gate = {}
        if not str(analysis_gate.get("summary") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Select a scenario source and click Analyze Scenario first",
            )

    practice_in = str(payload.get("practice_role", "") or "").strip().lower()
    if practice_in in ("buyer", "seller"):
        practice_role = practice_in
        if mode == "real_case":
            update_session_practice_role(session_id, practice_role)
    else:
        practice_role = str(session.get("practice_role") or "seller").lower()
        if practice_role not in ("buyer", "seller"):
            practice_role = "seller"

    analysis = mode_context.get("analysis", {}) if mode_context else {}

    context_parts: List[str] = []

    if analysis.get("summary"):
        context_parts.append(f"Summary: {analysis['summary']}")

    if analysis.get("key_points"):
        context_parts.append("Key points: " + "; ".join(analysis["key_points"]))

    if analysis.get("negotiation_points"):
        context_parts.append("Negotiation points: " + "; ".join(analysis["negotiation_points"]))

    if mode_context and mode_context.get("raw_text"):
        context_parts.append(f"Scenario text:\n{str(mode_context['raw_text'])[:6000]}")

    context_text = "\n\n".join(context_parts)

    user_audit_for_sse: Dict[str, Any] = {}
    if mode == "real_case" and message.strip():
        user_audit_for_sse = audit_real_case_user_message(message, context_text)
        if not isinstance(user_audit_for_sse, dict):
            user_audit_for_sse = {}

    if message:
        add_message(
            session_id,
            "module_2",
            mode,
            "user",
            message,
            audit=user_audit_for_sse if mode == "real_case" else None,
        )

    chat_payload: Dict[str, Any] = {"message": message, "context_text": context_text}
    if mode == "real_case":
        chat_payload["practice_role"] = practice_role
        chat_payload["analysis"] = analysis
        chat_payload["difficulty"] = payload.get("difficulty", "medium")
        chat_payload["mentor"] = payload.get("mentor", True)
        detail = get_session_detail(session_id)
        chat_payload["history_messages"] = detail.get("messages", [])

    result = run_chat(mode, action, chat_payload)

    reply = str(result["reply"])
    if mode == "real_case":
        audit_payload: Dict[str, Any] = {}
    else:
        audit_payload = result.get("audit") if isinstance(result.get("audit"), dict) else {}

    add_message(session_id, "module_2", mode, "assistant", reply, audit=audit_payload or {})
    mentor_insight = result.get("mentor_insight")
    mentor_text = str(mentor_insight).strip() if mentor_insight is not None else ""
    if mentor_text:
        add_message(session_id, "module_2", mode, "mentor", mentor_text)

    async def event_stream():
        for token in reply.split():
            yield f"data: {json.dumps({'token': token + ' '})}\n\n"
        yield f"data: {json.dumps({'done': True, 'audit': audit_payload, 'user_audit': user_audit_for_sse, 'mentor_insight': mentor_text})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# =========================
# SANDBOX SIMULATION
# =========================


def _validate_sim_api_hist(raw: Any) -> List[Dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="api_hist must be a list")
    if len(raw) > 44:
        raise HTTPException(status_code=400, detail="api_hist too long")
    out: List[Dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            raise HTTPException(status_code=400, detail="api_hist entries must be objects")
        r = m.get("role")
        c = m.get("content", "")
        if r not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail="Invalid message role in api_hist")
        if not isinstance(c, str):
            c = str(c)
        if len(c) > 12000:
            raise HTTPException(status_code=400, detail="Message content too long")
        out.append({"role": r, "content": c})
    if len(out) % 2 != 0:
        raise HTTPException(status_code=400, detail="api_hist must have even length")
    for idx, msg in enumerate(out):
        want = "user" if idx % 2 == 0 else "assistant"
        if msg["role"] != want:
            raise HTTPException(
                status_code=400,
                detail="api_hist must alternate user/assistant starting with user",
            )
    return out


@router.post("/api/sandbox/simulate-step")
async def api_sandbox_simulate_step(request: Request):
    user = _sync_db_user(request)
    payload = await request.json()

    session_id = str(payload.get("session_id", "")).strip()
    turns = int(payload.get("turns", 18))

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")

    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    mode_context = get_session_context(session_id, "sandbox")
    if not mode_context:
        raise HTTPException(status_code=400, detail="Prepare a scenario first")

    api_hist = _validate_sim_api_hist(payload.get("api_hist"))
    simulation_state_in = payload.get("simulation_state")
    if simulation_state_in is not None and not isinstance(simulation_state_in, dict):
        raise HTTPException(status_code=400, detail="simulation_state must be an object")
    analysis = mode_context.get("analysis", {})
    mentor_flag = payload.get("mentor", True)
    if isinstance(mentor_flag, str):
        mentor_flag = mentor_flag.strip().lower() in ("1", "true", "yes", "on")
    mentor_enabled = bool(mentor_flag)
    difficulty = str(payload.get("difficulty", "medium")).strip().lower()
    if difficulty not in {"simple", "medium", "hard"}:
        difficulty = "medium"

    result = run_sandbox_simulation_step(
        analysis,
        api_hist,
        simulation_state=simulation_state_in if isinstance(simulation_state_in, dict) else None,
        turns=turns,
        mentor=mentor_enabled,
        difficulty=difficulty,
    )
    if not mentor_enabled:
        # Safety: force-disable mentor content in API response and persistence.
        result["mentor_insight"] = None

    if result.get("item"):
        item = result["item"]
        add_message(session_id, "module_2", "sandbox", item["role"], item["text"])

    insight = result.get("mentor_insight")
    if insight and str(insight).strip():
        add_message(session_id, "module_2", "sandbox", "mentor", str(insight).strip())

    if result.get("item") and result.get("done") and result.get("audit"):
        add_message(
            session_id,
            "module_2",
            "sandbox",
            "system",
            result["audit"]["summary"],
            audit=result["audit"],
        )

    return JSONResponse(result)


@router.post("/api/sandbox/simulate")
async def api_sandbox_simulate(request: Request):
    user = _sync_db_user(request)
    payload = await request.json()

    session_id = str(payload.get("session_id", "")).strip()
    turns = int(payload.get("turns", 18))
    simulation_state_in = payload.get("simulation_state")
    if simulation_state_in is not None and not isinstance(simulation_state_in, dict):
        raise HTTPException(status_code=400, detail="simulation_state must be an object")

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")

    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    mode_context = get_session_context(session_id, "sandbox")
    if not mode_context:
        raise HTTPException(status_code=400, detail="Prepare a scenario first")

    analysis = mode_context.get("analysis", {})
    simulation = run_sandbox_simulation(
        analysis,
        turns=turns,
        simulation_state=simulation_state_in if isinstance(simulation_state_in, dict) else None,
    )

    stored_messages = [
        {"role": item["role"], "content": item["text"], "audit": {}}
        for item in simulation["transcript"]
    ]

    if simulation.get("audit"):
        stored_messages.append(
            {
                "role": "system",
                "content": simulation["audit"]["summary"],
                "audit": simulation["audit"],
            }
        )

    add_messages(session_id, "module_2", "sandbox", stored_messages)

    return JSONResponse({"ok": True, **simulation})


# =========================
# SESSION APIs
# =========================

@router.get("/api/session/{session_id}")
def api_session(request: Request, session_id: str):
    user = _sync_db_user(request)

    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    detail = get_session_detail(session_id)
    detail["context"] = _serialize_context(detail.get("context"))

    return JSONResponse(detail)


# =========================
# MANAGER DASHBOARD
# =========================

@router.get("/manager", response_class=HTMLResponse)
def manager_dashboard(request: Request):
    user = _sync_db_user(request)
    require_manager(request)

    context = _base_context(request)
    context.update(
        {
            "analytics": load_dashboard_data(),
            "user": user,
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="manager_dashboard.html",
        context=context,
    )


@router.get("/api/manager/analytics")
def api_manager_analytics(request: Request):
    _sync_db_user(request)
    require_manager(request)
    return JSONResponse(get_manager_analytics())