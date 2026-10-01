"""Agent tool layer: ToolDefinition, ToolRegistry, ToolExecutor.

Every tool performs a real operation against the project store, the sandbox
process table or the execution adapter. Tool results are the actual return
values — nothing is simulated.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..services import diff as diff_service
from ..services.execution import ExecutionAdapter
from ..services.filesystem import FilesystemAdapter
from ..services.preview import PreviewAdapter
from .. import repository


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., dict]
    mutating: bool = False
    verifiable: bool = False


@dataclass
class ToolRegistry:
    tools: dict[str, ToolDefinition] = field(default_factory=dict)

    def register(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self.tools.get(name)

    def describe(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters,
             "mutating": t.mutating, "verifiable": t.verifiable}
            for t in self.tools.values()
        ]


class ToolExecutor:
    """Executes tools and returns real, timestamped receipts."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, name: str, project_id: str, **kwargs: Any) -> dict:
        tool = self.registry.get(name)
        started = time.time()
        if tool is None:
            return {
                "tool": name, "status": "failed", "error": f"unknown tool '{name}'",
                "result": None, "durationMs": 0, "timestamp": started,
            }
        try:
            result = tool.handler(project_id, **kwargs)
            return {
                "tool": name, "status": "succeeded", "result": result, "error": "",
                "durationMs": int((time.time() - started) * 1000), "timestamp": started,
                "mutating": tool.mutating,
            }
        except Exception as exc:  # surface the real failure
            return {
                "tool": name, "status": "failed", "result": None, "error": str(exc),
                "durationMs": int((time.time() - started) * 1000), "timestamp": started,
                "mutating": tool.mutating,
            }


# --------------------------------------------------------------------------- #
# Tool implementations (real)
# --------------------------------------------------------------------------- #


def _read_file(project_id: str, path: str) -> dict:
    content = FilesystemAdapter(project_id).read(path)
    if content is None:
        raise FileNotFoundError(f"{path} not found")
    return {"path": path, "content": content, "bytes": len(content)}


def _write_file(project_id: str, path: str, content: str = "") -> dict:
    row = FilesystemAdapter(project_id).write(path, content)
    return {"path": row["path"], "bytes": len(content), "language": row["language"]}


def _create_file(project_id: str, path: str, content: str = "") -> dict:
    row = FilesystemAdapter(project_id).create(path, content)
    return {"path": row["path"], "created": True}


def _edit_file(project_id: str, path: str, find: str, replace: str) -> dict:
    row = FilesystemAdapter(project_id).edit(path, find, replace)
    return {"path": row["path"], "bytes": len(row["content"] or "")}


def _delete_file(project_id: str, path: str) -> dict:
    removed = FilesystemAdapter(project_id).delete(path)
    return {"path": path, "removed": removed}


def _create_directory(project_id: str, path: str) -> dict:
    row = FilesystemAdapter(project_id).create_directory(path)
    return {"path": row["path"], "isDir": True}


def _list_files(project_id: str) -> dict:
    tree = FilesystemAdapter(project_id).tree()
    return {"count": len(tree), "files": tree}


def _search_files(project_id: str, term: str, content: bool = False) -> dict:
    matches = FilesystemAdapter(project_id).search(term, content=content)
    return {"term": term, "count": len(matches),
            "matches": [{"path": m["path"], "isDir": bool(m["is_dir"])} for m in matches]}


def _get_project_info(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise FileNotFoundError("project not found")
    files = FilesystemAdapter(project_id).list()
    tasks = repository.list_tasks(project_id)
    return {
        "project": {"id": project["id"], "name": project["name"], "template": project["template"],
                    "status": project["status"], "description": project["description"]},
        "fileCount": len([f for f in files if not f["is_dir"]]),
        "directoryCount": len([f for f in files if f["is_dir"]]),
        "taskCount": len(tasks),
        "capabilities": ExecutionAdapter.capabilities(),
    }


def _get_diff(project_id: str) -> dict:
    return diff_service.compute_diff(project_id)


def _run_tests(project_id: str, timeout: int = 180) -> dict:
    from ..services import verification
    result = verification.verify_tests(project_id, timeout=timeout)
    return {"status": result["status"], "method": result["method"],
            "evidence": result["evidence"], "error": result["error"]}


def _start_preview(project_id: str, command: str | None = None) -> dict:
    return PreviewAdapter(project_id).start(command)


def _stop_preview(project_id: str) -> dict:
    return PreviewAdapter(project_id).stop()


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        "read_file", "Read a file's contents from the project store.",
        {"path": "string"}, _read_file))
    registry.register(ToolDefinition(
        "write_file", "Overwrite a file's contents (creates it if missing).",
        {"path": "string", "content": "string"}, _write_file, mutating=True, verifiable=True))
    registry.register(ToolDefinition(
        "create_file", "Create a new file with initial content.",
        {"path": "string", "content": "string"}, _create_file, mutating=True, verifiable=True))
    registry.register(ToolDefinition(
        "edit_file", "Replace an exact snippet in a file.",
        {"path": "string", "find": "string", "replace": "string"}, _edit_file,
        mutating=True, verifiable=True))
    registry.register(ToolDefinition(
        "delete_file", "Delete a file (or directory tree) from the project store.",
        {"path": "string"}, _delete_file, mutating=True))
    registry.register(ToolDefinition(
        "create_directory", "Create a directory node.",
        {"path": "string"}, _create_directory, mutating=True))
    registry.register(ToolDefinition(
        "list_files", "List every file and directory node in the project.", {}, _list_files))
    registry.register(ToolDefinition(
        "search_files", "Search project paths (and optionally contents).",
        {"term": "string", "content": "boolean"}, _search_files))
    registry.register(ToolDefinition(
        "get_project_info", "Summarise the project and sandbox capabilities.", {},
        _get_project_info))
    registry.register(ToolDefinition(
        "get_diff", "Compute the current change set from stored versions.", {}, _get_diff))
    registry.register(ToolDefinition(
        "run_tests", "Run the project's real test command and return its result.",
        {"timeout": "integer"}, _run_tests))
    registry.register(ToolDefinition(
        "start_preview", "Start the project's preview process.",
        {"command": "string"}, _start_preview, mutating=True))
    registry.register(ToolDefinition(
        "stop_preview", "Stop the project's preview process.", {}, _stop_preview))
    return registry


REGISTRY = build_registry()
EXECUTOR = ToolExecutor(REGISTRY)
