"""ExecutionAdapter — real command execution inside the sandbox.

Commands genuinely run (subprocess) against a materialized copy of the project.
Results are real stdout/stderr/exit codes — never synthesised. Capabilities are
probed from the actual environment so the UI can state honestly what can run.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .filesystem import FilesystemAdapter

# Commands that must never be run through the workspace terminal.
BLOCKED = ("rm -rf /", "mkfs", ":(){", "shutdown", "reboot", "halt", "dd if=")


class ExecutionAdapter:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.fs = FilesystemAdapter(project_id)

    # -- capability discovery (real) --------------------------------------- #
    @staticmethod
    def capabilities() -> dict:
        return {
            "shell": True,
            "python": shutil.which("python3") is not None,
            "node": shutil.which("node") is not None,
            "npm": shutil.which("npm") is not None,
            "git": shutil.which("git") is not None,
            "pytest": shutil.which("pytest") is not None,
        }

    def run(self, command: str, cwd: str | None = None, timeout: int = 120) -> dict:
        if any(token in command for token in BLOCKED):
            return {
                "status": "blocked",
                "command": command,
                "stdout": "",
                "stderr": "command blocked by the workspace safety policy",
                "exitCode": None,
                "durationMs": 0,
                "timedOut": False,
            }

        workspace = self.fs.materialize()
        working_dir = Path(cwd) if cwd else workspace
        started = time.time()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = int((time.time() - started) * 1000)
            return {
                "status": "succeeded" if completed.returncode == 0 else "failed",
                "command": command,
                "stdout": completed.stdout[-20000:],
                "stderr": completed.stderr[-20000:],
                "exitCode": completed.returncode,
                "durationMs": duration,
                "timedOut": False,
            }
        except subprocess.TimeoutExpired as exc:
            duration = int((time.time() - started) * 1000)
            return {
                "status": "timed_out",
                "command": command,
                "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": f"command exceeded the {timeout}s timeout",
                "exitCode": None,
                "durationMs": duration,
                "timedOut": True,
            }
        except OSError as exc:
            return {
                "status": "failed",
                "command": command,
                "stdout": "",
                "stderr": str(exc),
                "exitCode": None,
                "durationMs": int((time.time() - started) * 1000),
                "timedOut": False,
            }
