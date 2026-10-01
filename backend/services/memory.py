"""Project memory — persists context that later AI requests genuinely reuse."""
from __future__ import annotations

import json

from .. import repository
from .filesystem import FilesystemAdapter


def remember(project_id: str, kind: str, content: str) -> dict:
    return repository.add_memory(project_id, kind, content)


def snapshot(project_id: str) -> dict:
    project = repository.get_project(project_id) or {}
    files = FilesystemAdapter(project_id).list()
    tasks = repository.list_tasks(project_id)
    verifications = repository.list_verifications(project_id)
    memory = repository.list_memory(project_id)

    return {
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "description": project.get("description"),
            "template": project.get("template"),
            "status": project.get("status"),
            "currentTask": project.get("current_task"),
        },
        "structure": [row["path"] for row in files if not row["is_dir"]],
        "keyFiles": [row["path"] for row in files if not row["is_dir"]][:12],
        "tasks": [
            {"title": t["title"], "state": t["state"], "stage": t["stage"]} for t in tasks[-20:]
        ],
        "errors": [
            {"claim": v["claim"], "error": v["error"], "status": v["status"]}
            for v in verifications if v["status"] == "failed"
        ][:10],
        "verifications": [
            {"claim": v["claim"], "status": v["status"], "method": v["method"]}
            for v in verifications[:10]
        ],
        "decisions": [{"kind": m["kind"], "content": m["content"]} for m in memory[:20]],
    }


def build_context(project_id: str, max_files: int = 12, max_chars: int = 8000) -> str:
    """A compact, relevant context string for the AI (kept small to limit usage)."""
    snapshot_data = snapshot(project_id)
    adapter = FilesystemAdapter(project_id)

    parts = [
        f"Project: {snapshot_data['project']['name']} ({snapshot_data['project']['template']})",
        f"Description: {snapshot_data['project']['description'] or '(none)'}",
        f"Status: {snapshot_data['project']['status']}; current task: "
        f"{snapshot_data['project']['currentTask'] or '(idle)'}",
        f"Files ({len(snapshot_data['structure'])}): "
        + ", ".join(snapshot_data["structure"][:40]),
    ]

    budget = max_chars
    included = 0
    for path in snapshot_data["keyFiles"]:
        if included >= max_files or budget <= 0:
            break
        content = adapter.read(path) or ""
        snippet = content[:1500]
        budget -= len(snippet)
        parts.append(f"\n--- {path} ---\n{snippet}")
        included += 1

    if snapshot_data["decisions"]:
        parts.append(
            "\nApproved decisions:\n"
            + "\n".join(f"- {d['content']}" for d in snapshot_data["decisions"][-5:])
        )
    if snapshot_data["verifications"]:
        parts.append(
            "\nRecent verification:\n"
            + "\n".join(
                f"- [{v['status']}] {v['claim']} ({v['method']})"
                for v in snapshot_data["verifications"][:5]
            )
        )
    return "\n".join(parts)


def context_json(project_id: str) -> str:
    return json.dumps(snapshot(project_id), indent=2)
