"""PreviewAdapter — real process management for project previews.

Starts a genuine process in a materialized workspace and reports its real state.
Ports are drawn from the range published by docker-compose so the resulting URL
is reachable. If the project cannot be started with the available toolchain the
adapter says so instead of pretending.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from .. import repository
from .execution import ExecutionAdapter
from .filesystem import FilesystemAdapter

PORT_RANGE = range(
    int(os.environ.get("NEXORA_PREVIEW_PORT_START", "4100")),
    int(os.environ.get("NEXORA_PREVIEW_PORT_END", "4103")) + 1,
)
PUBLIC_SUFFIX = os.environ.get("BASE44_PUBLIC_HOST_SUFFIX", "localhost")

_registry: dict[str, dict] = {}
_lock = threading.Lock()


def _detect_command(project: dict, files: list[dict]) -> str | None:
    """Choose a real start command from the project's actual files."""
    paths = {row["path"] for row in files}
    capabilities = ExecutionAdapter.capabilities()
    if "package.json" in paths and capabilities.get("npm"):
        return f"npm install && npm run dev -- --host 0.0.0.0 --port $PORT"
    for entry in ("app.py", "main.py"):
        if entry in paths:
            return f"PORT=$PORT python3 {entry}"
    return None


class PreviewAdapter:
    def __init__(self, project_id: str):
        self.project_id = project_id

    def status(self) -> dict:
        with _lock:
            entry = _registry.get(self.project_id)
        if not entry:
            return {"running": False, "url": None, "port": None, "command": None,
                    "startedAt": None, "pid": None}
        alive = entry["process"].poll() is None
        return {
            "running": alive,
            "url": entry["url"] if alive else None,
            "port": entry["port"],
            "command": entry["command"],
            "startedAt": entry["started_at"],
            "pid": entry["process"].pid,
        }

    def start(self, command: str | None = None) -> dict:
        current = self.status()
        if current["running"]:
            return current

        project = repository.get_project(self.project_id) or {}
        fs = FilesystemAdapter(self.project_id)
        resolved = command or _detect_command(project, fs.list())
        if not resolved:
            return {
                "running": False, "url": None, "port": None, "command": None,
                "startedAt": None, "pid": None,
                "error": "No runnable entry point detected. This project needs an external "
                         "execution backend (or a matching runtime) to start a preview.",
            }

        with _lock:
            used = {entry["port"] for entry in _registry.values()}
            port = next((p for p in PORT_RANGE if p not in used), None)
        if port is None:
            return {"running": False, "url": None, "port": None, "command": resolved,
                    "startedAt": None, "pid": None, "error": "No preview ports available."}

        workspace = fs.materialize()
        env = dict(os.environ, PORT=str(port))
        try:
            process = subprocess.Popen(
                resolved, shell=True, cwd=str(workspace), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                preexec_fn=os.setsid,
            )
        except OSError as exc:
            return {"running": False, "url": None, "port": port, "command": resolved,
                    "startedAt": None, "pid": None, "error": str(exc)}

        url = f"https://{port}-{PUBLIC_SUFFIX}"
        with _lock:
            _registry[self.project_id] = {
                "process": process, "port": port, "command": resolved,
                "url": url, "started_at": time.time(), "workspace": str(workspace),
            }
        time.sleep(1.0)
        result = self.status()
        result["command"] = resolved
        return result

    def stop(self) -> dict:
        with _lock:
            entry = _registry.pop(self.project_id, None)
        if not entry:
            return {"running": False, "url": None, "port": None, "command": None,
                    "startedAt": None, "pid": None}
        process = entry["process"]
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except OSError:
                pass
        return {"running": False, "url": None, "port": entry["port"],
                "command": entry["command"], "startedAt": None, "pid": process.pid}
