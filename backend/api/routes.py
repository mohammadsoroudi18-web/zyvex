"""HTTP API for the NEXORA workspace."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import repository
from ..agents import roles as roles_module
from ..agents.runtime import AgentRuntime
from ..agents.tools import REGISTRY
from ..ai.providers import AIError, provider_catalog
from ..ai.service import AIService
from ..services import memory, templates
from ..services.diff import compute_diff
from ..services.execution import ExecutionAdapter
from ..services.filesystem import FilesystemAdapter
from ..services.preview import PreviewAdapter

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    template: str = "empty"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template: str | None = None
    status: str | None = None
    current_task: str | None = None


class FileWrite(BaseModel):
    path: str
    content: str = ""


class FileRename(BaseModel):
    path: str
    new_path: str


class PathBody(BaseModel):
    path: str


class ChatBody(BaseModel):
    message: str
    role: str = "coding"


class EnhanceBody(BaseModel):
    prompt: str


class PlanBody(BaseModel):
    request: str


class AgentBody(BaseModel):
    request: str
    mode: str = "build"
    role: str = "coding"
    auto_fix: bool = True


class TerminalBody(BaseModel):
    command: str
    timeout: int = 120


class PreviewBody(BaseModel):
    command: str | None = None


class SettingsBody(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    theme: str | None = None
    accent: str | None = None
    default_template: str | None = None
    shortcut_enhance: str | None = None
    shortcut_send: str | None = None
    auto_plan: bool | None = None
    auto_verify: bool | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _require_project(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


# --------------------------------------------------------------------------- #
# System / meta
# --------------------------------------------------------------------------- #


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nexora-ai-builder"}


@router.get("/system")
def system() -> dict:
    settings = repository.get_settings()
    return {
        "capabilities": ExecutionAdapter.capabilities(),
        "providers": provider_catalog(settings),
        "templates": templates.template_catalog(),
        "roles": roles_module.role_catalog(),
        "tools": REGISTRY.describe(),
        "settings": settings,
        "externalBackends": [
            {
                "id": "execution",
                "label": "Execution backend",
                "supported": True,
                "note": "Commands run for real inside this sandbox container. Runtimes absent "
                        "from the container image (e.g. Node/npm) require a runner image.",
            },
            {
                "id": "preview",
                "label": "Preview",
                "supported": True,
                "note": "Previews start as real processes on published ports when the project "
                        "has a runnable entry point.",
            },
        ],
    }


@router.get("/tools")
def tools() -> dict:
    return {"tools": REGISTRY.describe()}


@router.get("/roles")
def roles() -> dict:
    return {"roles": roles_module.role_catalog()}


@router.get("/templates")
def templates_endpoint() -> dict:
    return {"templates": templates.template_catalog()}


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #


@router.get("/projects")
def list_projects(search: str = "") -> dict:
    return {"projects": repository.list_projects(search)}


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate) -> dict:
    project = repository.create_project(body.name, body.description, body.template)
    templates.scaffold(project["id"], body.template)
    memory.remember(project["id"], "decision",
                    f"Created from template '{body.template}'.")
    return {"project": repository.get_project(project["id"])}


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    return {"project": _require_project(project_id)}


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdate) -> dict:
    _require_project(project_id)
    project = repository.update_project(project_id, **body.model_dump(exclude_none=True))
    return {"project": project}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    _require_project(project_id)
    repository.delete_project(project_id)
    return {"deleted": project_id}


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/files")
def list_files(project_id: str) -> dict:
    _require_project(project_id)
    adapter = FilesystemAdapter(project_id)
    return {"files": adapter.tree(), "count": len(adapter.list())}


@router.get("/projects/{project_id}/file")
def read_file(project_id: str, path: str) -> dict:
    _require_project(project_id)
    row = repository.get_file(project_id, path)
    if not row:
        raise HTTPException(status_code=404, detail="file not found")
    return {"file": row}


@router.put("/projects/{project_id}/file")
def write_file(project_id: str, body: FileWrite) -> dict:
    _require_project(project_id)
    return {"file": FilesystemAdapter(project_id).write(body.path, body.content)}


@router.post("/projects/{project_id}/file", status_code=201)
def create_file(project_id: str, body: FileWrite) -> dict:
    _require_project(project_id)
    return {"file": FilesystemAdapter(project_id).create(body.path, body.content)}


@router.post("/projects/{project_id}/directory", status_code=201)
def create_directory(project_id: str, body: PathBody) -> dict:
    _require_project(project_id)
    return {"file": FilesystemAdapter(project_id).create_directory(body.path)}


@router.post("/projects/{project_id}/rename")
def rename_file(project_id: str, body: FileRename) -> dict:
    _require_project(project_id)
    row = FilesystemAdapter(project_id).rename(body.path, body.new_path)
    if not row:
        raise HTTPException(status_code=404, detail="file not found")
    return {"file": row}


@router.delete("/projects/{project_id}/file")
def delete_file(project_id: str, path: str) -> dict:
    _require_project(project_id)
    return {"removed": FilesystemAdapter(project_id).delete(path)}


@router.get("/projects/{project_id}/search")
def search_files(project_id: str, term: str, content: bool = False) -> dict:
    _require_project(project_id)
    matches = FilesystemAdapter(project_id).search(term, content=content)
    return {"matches": [{"path": m["path"], "isDir": bool(m["is_dir"])} for m in matches]}


@router.post("/projects/{project_id}/refresh")
def refresh_workspace(project_id: str) -> dict:
    _require_project(project_id)
    adapter = FilesystemAdapter(project_id)
    workspace = adapter.materialize()
    return {"materialized": str(workspace), "files": len(adapter.tree())}


# --------------------------------------------------------------------------- #
# AI: chat / enhance / plan / agent
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/messages")
def list_messages(project_id: str) -> dict:
    _require_project(project_id)
    conversation = repository.get_or_create_conversation(project_id)
    return {"conversation": conversation, "messages": repository.list_messages(conversation["id"])}


@router.post("/projects/{project_id}/chat")
def chat(project_id: str, body: ChatBody) -> dict:
    _require_project(project_id)
    conversation = repository.get_or_create_conversation(project_id)
    repository.add_message(project_id, conversation["id"], "user", body.message)
    service = AIService(repository.get_settings())
    try:
        reply = service.chat(
            [{"role": "user", "content": body.message}],
            context=memory.build_context(project_id),
        )
    except AIError as exc:
        assistant = repository.add_message(
            project_id, conversation["id"], "assistant",
            f"AI request could not be completed: {exc}",
            meta={"error": True},
        )
        return {"message": assistant, "aiAvailable": service.available, "error": str(exc)}
    assistant = repository.add_message(
        project_id, conversation["id"], "assistant", reply["text"],
        meta={"provider": reply.get("provider"), "model": reply.get("model"),
              "usage": reply.get("usage", {})},
    )
    return {"message": assistant, "aiAvailable": True}


@router.post("/projects/{project_id}/enhance")
def enhance(project_id: str, body: EnhanceBody) -> dict:
    _require_project(project_id)
    service = AIService(repository.get_settings())
    try:
        result = service.enhance_prompt(body.prompt, context=memory.build_context(project_id))
    except AIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "original": body.prompt,
        "enhanced": result["text"],
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


@router.post("/projects/{project_id}/plan")
def plan(project_id: str, body: PlanBody) -> dict:
    _require_project(project_id)
    runtime = AgentRuntime(project_id, repository.get_settings())
    return runtime.run(body.request, mode="plan")


@router.post("/projects/{project_id}/agent")
def agent(project_id: str, body: AgentBody) -> dict:
    _require_project(project_id)
    runtime = AgentRuntime(project_id, repository.get_settings())
    return runtime.run(body.request, mode=body.mode, role=body.role, auto_fix=body.auto_fix)


# --------------------------------------------------------------------------- #
# Tasks / verifications / diff / memory
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/tasks")
def tasks(project_id: str) -> dict:
    _require_project(project_id)
    return {"tasks": repository.list_tasks(project_id)}


@router.get("/projects/{project_id}/verifications")
def verifications(project_id: str) -> dict:
    _require_project(project_id)
    return {"verifications": repository.list_verifications(project_id)}


@router.get("/projects/{project_id}/diff")
def diff(project_id: str) -> dict:
    _require_project(project_id)
    return compute_diff(project_id)


@router.get("/projects/{project_id}/memory")
def memory_endpoint(project_id: str) -> dict:
    _require_project(project_id)
    return memory.snapshot(project_id)


# --------------------------------------------------------------------------- #
# Terminal / preview
# --------------------------------------------------------------------------- #


@router.post("/projects/{project_id}/terminal")
def terminal(project_id: str, body: TerminalBody) -> dict:
    _require_project(project_id)
    return ExecutionAdapter(project_id).run(body.command, timeout=body.timeout)


@router.get("/projects/{project_id}/preview")
def preview_status(project_id: str) -> dict:
    _require_project(project_id)
    return PreviewAdapter(project_id).status()


@router.post("/projects/{project_id}/preview")
def preview_start(project_id: str, body: PreviewBody) -> dict:
    _require_project(project_id)
    return PreviewAdapter(project_id).start(body.command)


@router.delete("/projects/{project_id}/preview")
def preview_stop(project_id: str) -> dict:
    _require_project(project_id)
    return PreviewAdapter(project_id).stop()


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


@router.get("/settings")
def get_settings() -> dict:
    settings = repository.get_settings()
    return {"settings": settings, "providers": provider_catalog(settings)}


@router.put("/settings")
def update_settings(body: SettingsBody) -> dict:
    settings = repository.save_settings(body.model_dump(exclude_none=True))
    return {"settings": settings, "providers": provider_catalog(settings)}
