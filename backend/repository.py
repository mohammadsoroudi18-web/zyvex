"""Entity repository — all persistence operations in one focused module."""
from __future__ import annotations

import json
from typing import Any

from . import db

# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #

PROJECT_FIELDS = {"name", "description", "template", "status", "current_task"}


def list_projects(search: str = "") -> list[dict]:
    if search:
        like = f"%{search.lower()}%"
        return db.query(
            "SELECT * FROM projects WHERE lower(name) LIKE ? OR lower(description) LIKE ? "
            "ORDER BY updated_at DESC",
            (like, like),
        )
    return db.query("SELECT * FROM projects ORDER BY updated_at DESC")


def get_project(project_id: str) -> dict | None:
    return db.query_one("SELECT * FROM projects WHERE id = ?", (project_id,))


def create_project(name: str, description: str = "", template: str = "empty") -> dict:
    project_id = db.new_id()
    ts = db.now()
    db.execute(
        "INSERT INTO projects (id, name, description, template, status, current_task, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (project_id, name, description, template, "idle", "", ts, ts),
    )
    return get_project(project_id)


def update_project(project_id: str, **fields: Any) -> dict | None:
    sets, params = [], []
    for key, value in fields.items():
        if key in PROJECT_FIELDS and value is not None:
            sets.append(f"{key} = ?")
            params.append(value)
    if sets:
        sets.append("updated_at = ?")
        params.append(db.now())
        params.append(project_id)
        db.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_project(project_id)


def touch_project(project_id: str) -> None:
    db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (db.now(), project_id))


def delete_project(project_id: str) -> None:
    for table in (
        "files",
        "file_versions",
        "conversations",
        "messages",
        "tasks",
        "verifications",
        "memory",
    ):
        db.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #

LANGUAGES = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".json": "json", ".md": "markdown", ".html": "html",
    ".css": "css", ".scss": "scss", ".yml": "yaml", ".yaml": "yaml", ".sh": "shell",
    ".sql": "sql", ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
    ".txt": "plaintext",
}


def language_for(path: str) -> str:
    lowered = path.lower()
    for suffix, language in LANGUAGES.items():
        if lowered.endswith(suffix):
            return language
    return "plaintext"


def list_files(project_id: str) -> list[dict]:
    return db.query(
        "SELECT * FROM files WHERE project_id = ? ORDER BY path ASC", (project_id,)
    )


def get_file(project_id: str, path: str) -> dict | None:
    return db.query_one(
        "SELECT * FROM files WHERE project_id = ? AND path = ?", (project_id, path)
    )


def _record_version(project_id: str, path: str, change: str, content: str) -> None:
    db.execute(
        "INSERT INTO file_versions (id, project_id, path, change, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (db.new_id(), project_id, path, change, content, db.now()),
    )


def _ensure_parent_dirs(project_id: str, path: str) -> None:
    parts = path.split("/")[:-1]
    prefix = ""
    for part in parts:
        prefix = f"{prefix}{part}" if not prefix else f"{prefix}/{part}"
        if not get_file(project_id, prefix):
            ts = db.now()
            db.execute(
                "INSERT INTO files (id, project_id, path, name, is_dir, content, language, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 1, '', 'plaintext', ?, ?)",
                (db.new_id(), project_id, prefix, part, ts, ts),
            )


def create_file(project_id: str, path: str, content: str = "", is_dir: bool = False) -> dict:
    path = path.strip("/")
    existing = get_file(project_id, path)
    if existing:
        return existing
    _ensure_parent_dirs(project_id, path)
    ts = db.now()
    db.execute(
        "INSERT INTO files (id, project_id, path, name, is_dir, content, language, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            db.new_id(), project_id, path, path.split("/")[-1], 1 if is_dir else 0,
            "" if is_dir else content, "plaintext" if is_dir else language_for(path), ts, ts,
        ),
    )
    _record_version(project_id, path, "added", "" if is_dir else content)
    touch_project(project_id)
    return get_file(project_id, path)


def write_file(project_id: str, path: str, content: str) -> dict:
    existing = get_file(project_id, path)
    if not existing:
        return create_file(project_id, path, content)
    db.execute(
        "UPDATE files SET content = ?, language = ?, updated_at = ? WHERE project_id = ? AND path = ?",
        (content, language_for(path), db.now(), project_id, path),
    )
    _record_version(project_id, path, "modified", content)
    touch_project(project_id)
    return get_file(project_id, path)


def delete_file(project_id: str, path: str) -> int:
    target = get_file(project_id, path)
    if not target:
        return 0
    rows = [target]
    if target["is_dir"]:
        rows += db.query(
            "SELECT * FROM files WHERE project_id = ? AND path LIKE ?", (project_id, f"{path}/%")
        )
    for row in rows:
        if not row["is_dir"]:
            _record_version(project_id, row["path"], "deleted", row["content"])
        db.execute("DELETE FROM files WHERE id = ?", (row["id"],))
    touch_project(project_id)
    return len(rows)


def rename_file(project_id: str, path: str, new_path: str) -> dict | None:
    new_path = new_path.strip("/")
    target = get_file(project_id, path)
    if not target:
        return None
    if target["is_dir"]:
        children = db.query(
            "SELECT * FROM files WHERE project_id = ? AND path LIKE ?", (project_id, f"{path}/%")
        )
        for child in children:
            child_new = child["path"].replace(path, new_path, 1)
            db.execute("UPDATE files SET path = ? WHERE id = ?", (child_new, child["id"]))
    _ensure_parent_dirs(project_id, new_path)
    db.execute(
        "UPDATE files SET path = ?, name = ?, updated_at = ? WHERE id = ?",
        (new_path, new_path.split("/")[-1], db.now(), target["id"]),
    )
    touch_project(project_id)
    return get_file(project_id, new_path)


def search_files(project_id: str, term: str, content_search: bool = False) -> list[dict]:
    like = f"%{term.lower()}%"
    if content_search:
        return db.query(
            "SELECT * FROM files WHERE project_id = ? AND is_dir = 0 AND "
            "(lower(path) LIKE ? OR lower(content) LIKE ?) ORDER BY path",
            (project_id, like, like),
        )
    return db.query(
        "SELECT * FROM files WHERE project_id = ? AND lower(path) LIKE ? ORDER BY path",
        (project_id, like),
    )


def list_versions(project_id: str, path: str | None = None) -> list[dict]:
    if path:
        return db.query(
            "SELECT * FROM file_versions WHERE project_id = ? AND path = ? ORDER BY created_at ASC",
            (project_id, path),
        )
    return db.query(
        "SELECT * FROM file_versions WHERE project_id = ? ORDER BY created_at ASC", (project_id,)
    )


# --------------------------------------------------------------------------- #
# Conversations & messages
# --------------------------------------------------------------------------- #


def get_or_create_conversation(project_id: str, title: str = "Workspace chat") -> dict:
    existing = db.query_one(
        "SELECT * FROM conversations WHERE project_id = ? ORDER BY created_at ASC LIMIT 1",
        (project_id,),
    )
    if existing:
        return existing
    conversation_id = db.new_id()
    db.execute(
        "INSERT INTO conversations (id, project_id, title, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, project_id, title, db.now()),
    )
    return db.query_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))


def add_message(project_id: str, conversation_id: str, role: str, content: str,
                meta: dict | None = None) -> dict:
    message_id = db.new_id()
    db.execute(
        "INSERT INTO messages (id, project_id, conversation_id, role, content, meta, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message_id, project_id, conversation_id, role, content, json.dumps(meta or {}), db.now()),
    )
    return db.query_one("SELECT * FROM messages WHERE id = ?", (message_id,))


def list_messages(conversation_id: str, limit: int = 200) -> list[dict]:
    rows = db.query(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,)
    )
    return rows[-limit:]


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #

TASK_FIELDS = {
    "title", "description", "state", "stage", "depends_on", "attempt", "max_retries",
    "timeout", "logs", "receipt", "started_at", "finished_at", "parent_id",
}


def create_task(project_id: str, title: str, description: str = "", stage: str = "execute",
                depends_on: list | None = None, parent_id: str | None = None,
                max_retries: int = 1, timeout: int = 120) -> dict:
    task_id = db.new_id()
    ts = db.now()
    db.execute(
        "INSERT INTO tasks (id, project_id, parent_id, title, description, state, stage, "
        "depends_on, attempt, max_retries, timeout, logs, receipt, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'planned', ?, ?, 0, ?, ?, '[]', '{}', ?, ?)",
        (
            task_id, project_id, parent_id, title, description, stage,
            json.dumps(depends_on or []), max_retries, timeout, ts, ts,
        ),
    )
    return get_task(task_id)


def get_task(task_id: str) -> dict | None:
    return db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))


def list_tasks(project_id: str) -> list[dict]:
    return db.query(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,)
    )


def update_task(task_id: str, **fields: Any) -> dict | None:
    sets, params = [], []
    for key, value in fields.items():
        if key in TASK_FIELDS:
            if key in ("depends_on", "logs", "receipt") and not isinstance(value, str):
                value = json.dumps(value)
            sets.append(f"{key} = ?")
            params.append(value)
    sets.append("updated_at = ?")
    params.append(db.now())
    params.append(task_id)
    db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_task(task_id)


def append_task_log(task_id: str, entry: dict) -> None:
    task = get_task(task_id)
    if not task:
        return
    logs = json.loads(task["logs"] or "[]")
    logs.append(entry)
    db.execute("UPDATE tasks SET logs = ? WHERE id = ?", (json.dumps(logs), task_id))


# --------------------------------------------------------------------------- #
# Verifications
# --------------------------------------------------------------------------- #


def add_verification(project_id: str, task_id: str | None, claim: str, method: str,
                     status: str, evidence: dict, error: str = "") -> dict:
    verification_id = db.new_id()
    db.execute(
        "INSERT INTO verifications (id, project_id, task_id, claim, method, status, evidence, "
        "error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            verification_id, project_id, task_id, claim, method, status,
            json.dumps(evidence), error, db.now(),
        ),
    )
    return db.query_one("SELECT * FROM verifications WHERE id = ?", (verification_id,))


def list_verifications(project_id: str) -> list[dict]:
    return db.query(
        "SELECT * FROM verifications WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
    )


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #


def add_memory(project_id: str, kind: str, content: str) -> dict:
    memory_id = db.new_id()
    db.execute(
        "INSERT INTO memory (id, project_id, kind, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (memory_id, project_id, kind, content, db.now()),
    )
    return db.query_one("SELECT * FROM memory WHERE id = ?", (memory_id,))


def list_memory(project_id: str, limit: int = 200) -> list[dict]:
    return db.query(
        "SELECT * FROM memory WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
        (project_id, limit),
    )


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

DEFAULT_SETTINGS: dict[str, Any] = {
    "provider": "anthropic",
    "model": "",
    "base_url": "",
    "temperature": 0.2,
    "max_tokens": 4096,
    "theme": "dark",
    "accent": "indigo",
    "default_template": "empty",
    "shortcut_enhance": "Ctrl+Shift+E",
    "shortcut_send": "Ctrl+Enter",
    "auto_plan": True,
    "auto_verify": True,
}


def get_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    for row in db.query("SELECT key, value FROM settings"):
        try:
            settings[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            settings[row["key"]] = row["value"]
    return settings


def save_settings(patch: dict) -> dict:
    for key, value in patch.items():
        if key in DEFAULT_SETTINGS:
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
    return get_settings()
