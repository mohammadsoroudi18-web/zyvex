"""Evidence-based verification.

A claim is only marked verified when a real check confirms it. The AI asserting
success is never sufficient.
"""
from __future__ import annotations

from .execution import ExecutionAdapter
from .filesystem import FilesystemAdapter
from .preview import PreviewAdapter

VERIFIED = "verified"
FAILED = "failed"
UNVERIFIED = "unverified"


def verify_file_exists(project_id: str, path: str) -> dict:
    adapter = FilesystemAdapter(project_id)
    exists = adapter.exists(path)
    return {
        "status": VERIFIED if exists else FAILED,
        "method": "file_store.exists",
        "evidence": {"path": path, "exists": exists},
        "error": "" if exists else f"{path} was not found in the project store",
    }


def verify_command_result(project_id: str, result: dict) -> dict:
    if result.get("status") == "timed_out":
        return {"status": UNVERIFIED, "method": "execution",
                "evidence": {"exitCode": None, "timedOut": True},
                "error": "command timed out before producing a result"}
    if result.get("status") == "blocked":
        return {"status": UNVERIFIED, "method": "execution",
                "evidence": {"blocked": True}, "error": result.get("stderr", "")}
    passed = result.get("exitCode") == 0
    return {
        "status": VERIFIED if passed else FAILED,
        "method": "execution.exit_code",
        "evidence": {
            "command": result.get("command"),
            "exitCode": result.get("exitCode"),
            "durationMs": result.get("durationMs"),
            "stderr": (result.get("stderr") or "")[:1000],
        },
        "error": "" if passed else (result.get("stderr") or "command failed"),
    }


def verify_preview(project_id: str) -> dict:
    adapter = PreviewAdapter(project_id)
    status = adapter.status()
    if status["running"]:
        return {"status": VERIFIED, "method": "preview.process_alive",
                "evidence": {"url": status["url"], "pid": status["pid"]}, "error": ""}
    return {"status": UNVERIFIED, "method": "preview.process_alive",
            "evidence": {"running": False}, "error": "no preview process is running"}


def verify_tests(project_id: str, timeout: int = 180) -> dict:
    """Run the project's real test command and verify against its exit code."""
    capabilities = ExecutionAdapter.capabilities()
    adapter = FilesystemAdapter(project_id)
    paths = {row["path"] for row in adapter.list()}

    if "package.json" in paths and capabilities.get("npm"):
        result = ExecutionAdapter(project_id).run("npm test -- --run", timeout=timeout)
    elif capabilities.get("pytest"):
        result = ExecutionAdapter(project_id).run("python3 -m pytest -q", timeout=timeout)
    else:
        return {"status": UNVERIFIED, "method": "tests",
                "evidence": {"reason": "no test runner available in this sandbox"},
                "error": "No supported test runner is available for this project.", "result": None}

    verification = verify_command_result(project_id, result)
    verification["result"] = result
    return verification


def verify_build(project_id: str, timeout: int = 240) -> dict:
    capabilities = ExecutionAdapter.capabilities()
    adapter = FilesystemAdapter(project_id)
    paths = {row["path"] for row in adapter.list()}
    if "package.json" in paths and capabilities.get("npm"):
        result = ExecutionAdapter(project_id).run("npm install && npm run build", timeout=timeout)
    else:
        return {"status": UNVERIFIED, "method": "build",
                "evidence": {"reason": "no build toolchain available in this sandbox"},
                "error": "Build verification requires a matching toolchain (external execution "
                         "backend for this stack).", "result": None}
    verification = verify_command_result(project_id, result)
    verification["result"] = result
    return verification
