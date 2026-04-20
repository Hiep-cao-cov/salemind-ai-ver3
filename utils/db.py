"""
CRITICAL:
This file must contain ALL DB functions used across:
- routes.py
- rag.py
- dashboard.py
- modules

If adding new feature, update this file FIRST.
"""

import sqlite3
import uuid
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = "app.db"


# =========================
# CORE
# =========================

def now_iso():
    return datetime.utcnow().isoformat()


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================
# INIT DB
# =========================

def init_db():
    with get_connection() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            cwid TEXT UNIQUE,
            display_name TEXT,
            role TEXT,
            created_at TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            module_key TEXT,
            mode_key TEXT,
            title TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            module_key TEXT,
            mode_key TEXT,
            role TEXT,
            content TEXT,
            audit_json TEXT,
            created_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS session_context (
            session_id TEXT PRIMARY KEY,
            module_key TEXT,
            mode_key TEXT,
            source_type TEXT,
            source_name TEXT,
            raw_text TEXT,
            analysis_json TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS session_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            file_name TEXT,
            file_type TEXT,
            file_size INTEGER,
            created_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        )
        """)

        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN practice_role TEXT DEFAULT 'seller'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN difficulty TEXT DEFAULT 'medium'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN mentor_enabled INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN is_draft INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Legacy rows: practice_role omitted on INSERT used the column default (once 'buyer').
        try:
            conn.execute(
                "UPDATE sessions SET practice_role = 'seller' "
                "WHERE practice_role IS NULL OR TRIM(COALESCE(practice_role, '')) = ''"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "UPDATE sessions SET difficulty = 'medium' "
                "WHERE difficulty IS NULL OR TRIM(COALESCE(difficulty, '')) = ''"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "UPDATE sessions SET mentor_enabled = 1 WHERE mentor_enabled IS NULL"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("UPDATE sessions SET is_draft = 0 WHERE is_draft IS NULL")
        except sqlite3.OperationalError:
            pass


# =========================
# USER
# =========================

def upsert_user(cwid, display_name, role):
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE cwid=?",
            (cwid,)
        ).fetchone()

        if user:
            return dict(user)

        user_id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO users (id, cwid, display_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, cwid, display_name, role, now_iso()))

        return {
            "id": user_id,
            "cwid": cwid,
            "display_name": display_name,
            "role": role
        }


# =========================
# SESSION
# =========================

def create_session(user_id, module_key, mode_key, title, *, is_draft: bool = False):
    with get_connection() as conn:

        # ensure user exists
        user = conn.execute(
            "SELECT id FROM users WHERE id=?",
            (user_id,)
        ).fetchone()

        if not user:
            conn.execute("""
                INSERT INTO users (id, cwid, display_name, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, user_id, "Recovered User", "Unknown", now_iso()))

        session_id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO sessions
            (session_id, user_id, module_key, mode_key, title, created_at, updated_at, is_draft)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            user_id,
            module_key,
            mode_key,
            title,
            now_iso(),
            now_iso(),
            1 if is_draft else 0,
        ))

        # INSERT omits practice_role; older DBs used DEFAULT 'buyer' — set Covestro default explicitly.
        try:
            conn.execute(
                "UPDATE sessions SET practice_role=?, updated_at=? WHERE session_id=?",
                ("seller", now_iso(), session_id),
            )
        except sqlite3.OperationalError:
            pass

        return session_id


def get_session(session_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id=?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None


def update_session_mode(session_id, mode_key):
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET mode_key=?, updated_at=? WHERE session_id=?",
            (mode_key, now_iso(), session_id),
        )


def update_session_practice_role(session_id: str, practice_role: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET practice_role=?, updated_at=? WHERE session_id=?",
            (practice_role, now_iso(), session_id),
        )


def update_session_title(session_id: str, title: str, max_len: int = 72) -> None:
    t = (title or "").strip().replace("\n", " ")
    if not t:
        return
    if len(t) > max_len:
        t = t[: max_len - 1].rstrip() + "…"
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET title=?, updated_at=? WHERE session_id=?",
            (t, now_iso(), session_id),
        )


def update_session_ui_prefs(session_id: str, difficulty: str, mentor_enabled: bool) -> None:
    d = str(difficulty or "").strip().lower()
    if d not in ("simple", "medium", "hard"):
        d = "medium"
    m = 1 if bool(mentor_enabled) else 0
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET difficulty=?, mentor_enabled=?, updated_at=? WHERE session_id=?",
            (d, m, now_iso(), session_id),
        )


def mark_session_ready(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET is_draft=0, updated_at=? WHERE session_id=?",
            (now_iso(), session_id),
        )


def delete_draft_session_for_user(session_id: str, user_id: str) -> bool:
    session = get_session(session_id)
    if not session or str(session.get("user_id") or "") != str(user_id):
        return False
    if int(session.get("is_draft") or 0) != 1:
        return False
    with get_connection() as conn:
        msg_count = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id=?",
            (session_id,),
        ).fetchone()["c"]
        ctx_count = conn.execute(
            "SELECT COUNT(*) AS c FROM session_context WHERE session_id=?",
            (session_id,),
        ).fetchone()["c"]
        if msg_count or ctx_count:
            return False
        conn.execute("DELETE FROM session_files WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
    return True


def delete_session_for_user(session_id: str, user_id: str) -> bool:
    """
    Remove a session and all related rows. Returns True only if the session
    existed and belonged to user_id.
    """
    session = get_session(session_id)
    if not session or str(session.get("user_id") or "") != str(user_id):
        return False
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM session_files WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM session_context WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
    return True


def delete_messages_for_session_mode(session_id: str, module_key: str, mode_key: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM messages
            WHERE session_id=? AND module_key=? AND mode_key=?
            """,
            (session_id, module_key, mode_key),
        )


def delete_session_context_row(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM session_context WHERE session_id=?", (session_id,))


def delete_session_files_meta(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM session_files WHERE session_id=?", (session_id,))


# =========================
# MESSAGE
# =========================

def add_message(session_id, module_key, mode_key, role, content, audit=None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO messages
            (session_id, module_key, mode_key, role, content, audit_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            module_key,
            mode_key,
            role,
            content,
            json.dumps(audit or {}),
            now_iso(),
        ))


def add_messages(session_id, module_key, mode_key, messages):
    with get_connection() as conn:
        for m in messages:
            conn.execute("""
                INSERT INTO messages
                (session_id, module_key, mode_key, role, content, audit_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                module_key,
                mode_key,
                m.get("role"),
                m.get("content"),
                json.dumps(m.get("audit") or {}),
                now_iso(),
            ))


# =========================
# CONTEXT
# =========================

def upsert_session_context(
    session_id,
    module_key,
    mode_key,
    source_type,
    source_name,
    raw_text,
    analysis
):
    with get_connection() as conn:
        conn.execute("""
        INSERT INTO session_context
        (session_id, module_key, mode_key, source_type, source_name, raw_text, analysis_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            source_type=excluded.source_type,
            source_name=excluded.source_name,
            raw_text=excluded.raw_text,
            analysis_json=excluded.analysis_json
        """, (
            session_id,
            module_key,
            mode_key,
            source_type,
            source_name,
            raw_text,
            json.dumps(analysis),
        ))


def get_session_context(session_id, mode_key):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM session_context WHERE session_id=?",
            (session_id,)
        ).fetchone()

        if not row:
            return None

        data = dict(row)
        data["analysis"] = json.loads(data["analysis_json"] or "{}")
        return data


# =========================
# DETAIL / HISTORY
# =========================

def get_session_detail(
    session_id: str,
    *,
    module_key: str = "module_2",
    mode_key: Optional[str] = None,
):
    """
    Session messages + context. When ``mode_key`` is set, only messages for that
    workspace mode are returned (avoids mixing DEMO and Practice in one session).
    """
    with get_connection() as conn:
        if mode_key:
            messages = conn.execute(
                """
                SELECT role, content, audit_json, mode_key FROM messages
                WHERE session_id=? AND module_key=? AND mode_key=?
                ORDER BY id ASC
                """,
                (session_id, module_key, mode_key),
            ).fetchall()
        else:
            messages = conn.execute(
                """
                SELECT role, content, audit_json, mode_key FROM messages
                WHERE session_id=? AND module_key=?
                ORDER BY id ASC
                """,
                (session_id, module_key),
            ).fetchall()

        context = get_session_context(session_id, "")

        return {
            "messages": [dict(m) for m in messages],
            "context": context,
            "files": [],
        }


def list_recent_sessions_for_user(user_id, mode_key, limit=10):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                s.*,
                CASE
                    WHEN sc.analysis_json IS NOT NULL AND TRIM(COALESCE(sc.analysis_json, '')) <> ''
                    THEN 1 ELSE 0
                END AS has_context
            FROM sessions s
            LEFT JOIN session_context sc ON sc.session_id = s.session_id
            WHERE s.user_id=? AND s.mode_key=?
            ORDER BY created_at DESC, session_id DESC
            LIMIT ?
        """, (user_id, mode_key, limit)).fetchall()

        return [dict(r) for r in rows]


# =========================
# ANALYTICS
# =========================

def get_manager_analytics():
    with get_connection() as conn:
        total_users = conn.execute(
            "SELECT COUNT(*) AS count FROM users"
        ).fetchone()["count"]

        total_sessions = conn.execute(
            "SELECT COUNT(*) AS count FROM sessions"
        ).fetchone()["count"]

        total_messages = conn.execute(
            "SELECT COUNT(*) AS count FROM messages"
        ).fetchone()["count"]

        total_contexts = conn.execute(
            "SELECT COUNT(*) AS count FROM session_context"
        ).fetchone()["count"]

        sessions_by_mode_rows = conn.execute(
            """
            SELECT mode_key, COUNT(*) AS count
            FROM sessions
            GROUP BY mode_key
            ORDER BY count DESC
            """
        ).fetchall()

        sessions_by_mode = [
            {
                "mode_key": row["mode_key"],
                "count": row["count"],
            }
            for row in sessions_by_mode_rows
        ]

        top_users_rows = conn.execute(
            """
            SELECT
                u.display_name,
                u.cwid,
                u.role,
                COUNT(s.session_id) AS session_count
            FROM users u
            LEFT JOIN sessions s ON s.user_id = u.id
            GROUP BY u.id, u.display_name, u.cwid, u.role
            ORDER BY session_count DESC, u.display_name ASC
            LIMIT 10
            """
        ).fetchall()

        top_users = [
            {
                "display_name": row["display_name"],
                "cwid": row["cwid"],
                "role": row["role"],
                "session_count": row["session_count"],
            }
            for row in top_users_rows
        ]

        recent_sessions_rows = conn.execute(
            """
            SELECT
                s.session_id,
                s.title,
                s.module_key,
                s.mode_key,
                s.created_at,
                s.updated_at,
                u.display_name,
                u.cwid
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            ORDER BY s.updated_at DESC, s.created_at DESC
            LIMIT 10
            """
        ).fetchall()

        recent_sessions = [
            {
                "session_id": row["session_id"],
                "title": row["title"],
                "module_key": row["module_key"],
                "mode_key": row["mode_key"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "display_name": row["display_name"],
                "cwid": row["cwid"],
            }
            for row in recent_sessions_rows
        ]

        return {
            "totals": {
                "users": total_users,
                "sessions": total_sessions,
                "messages": total_messages,
                "contexts": total_contexts,
            },
            "sessions_by_mode": sessions_by_mode,
            "top_users": top_users,
            "recent_sessions": recent_sessions,
        }
def list_session_files(session_id):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT file_name, file_type, file_size, created_at
            FROM session_files
            WHERE session_id=?
            ORDER BY created_at DESC
        """, (session_id,)).fetchall()

        return [dict(r) for r in rows]
    
def save_session_file(session_id, file_name, file_type="unknown", file_size=0):
    with get_connection() as conn:
        conn.execute("""
        INSERT INTO session_files (session_id, file_name, file_type, file_size, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            file_name,
            file_type,
            file_size,
            now_iso(),
        ))