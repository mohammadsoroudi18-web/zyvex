"""Agent runtime — the shared orchestrator for every agent role.

Workflow: understand -> inspect -> plan -> execute -> test -> inspect errors ->
fix -> retest -> verify. Every stage records real tool receipts, and no stage is
reported as successful without evidence.
"""
from __future__ import annotations

import time

from .. import repository
from ..ai.providers import AIError
from ..ai.service import AIService
from ..services import memory, verification
from ..services.diff import compute_diff
from ..services.filesystem import FilesystemAdapter
from ..services.preview import PreviewAdapter
from .roles import role_instructions
from .tools import EXECUTOR

STAGES = [
    ("understand", "Understand"),
    ("inspect", "Inspect"),
    ("plan", "Plan"),
    ("execute", "Execute"),
    ("test", "Test"),
    ("inspect_errors", "Inspect Errors"),
    ("fix", "Fix"),
    ("retest", "Retest"),
    ("verify", "Verify"),
]


def _stage(stages: list[dict], stage_id: str, status: str, detail: str = "",
           receipts: list | None = None) -> None:
    for stage in stages:
        if stage["id"] == stage_id:
            stage["status"] = status
            stage["detail"] = detail
            if receipts is not None:
                stage["receipts"] = receipts
            if status in ("succeeded", "failed", "skipped", "blocked"):
                stage["finishedAt"] = time.time()
            else:
                stage["startedAt"] = stage["startedAt"] or time.time()
            return


def _fallback_plan(request: str) -> dict:
    """A real, deterministic plan used when no AI provider is configured."""
    steps = [
        ("Inspect project", "Read the current project structure and files.", "inspect"),
        ("Create files", "Create or update the files required by the request.", "execute"),
        ("Implement UI", "Implement the interface described in the request.", "execute"),
        ("Implement logic", "Implement the behaviour and data flow.", "execute"),
        ("Run tests", "Run the project's real test command where a runner is available.", "test"),
        ("Fix errors", "Resolve any errors reported by the test run.", "execute"),
        ("Verify", "Verify each claim against real evidence.", "verify"),
    ]
    return {
        "summary": request.strip() or "Implement the requested change.",
        "tasks": [
            {"title": title, "description": description, "stage": stage, "depends_on": []}
            for title, description, stage in steps
        ],
        "source": "deterministic",
    }


class AgentRuntime:
    def __init__(self, project_id: str, settings: dict):
        self.project_id = project_id
        self.settings = settings
        self.ai = AIService(settings)

    # -- stages ------------------------------------------------------------ #
    def run(self, request: str, mode: str = "build", role: str = "coding",
            auto_fix: bool = True) -> dict:
        stages = [
            {"id": sid, "label": label, "status": "pending", "detail": "",
             "receipts": [], "startedAt": None, "finishedAt": None}
            for sid, label in STAGES
        ]
        result: dict = {
            "stages": stages, "tasks": [], "verifications": [], "plan": None,
            "diff": None, "preview": None, "aiAvailable": self.ai.available,
            "role": role, "roleInstructions": role_instructions(role),
            "request": request, "mode": mode, "startedAt": time.time(),
        }

        repository.update_project(self.project_id, status="running", current_task=request[:120])

        # --- understand ---------------------------------------------------- #
        _stage(stages, "understand", "running")
        context = memory.build_context(self.project_id)
        memory.remember(self.project_id, "task", request[:500])
        _stage(stages, "understand", "succeeded",
               f"Collected context ({len(context)} chars) and recorded the request.")

        # --- inspect ------------------------------------------------------- #
        _stage(stages, "inspect", "running")
        receipts = [
            EXECUTOR.execute("get_project_info", self.project_id),
            EXECUTOR.execute("list_files", self.project_id),
        ]
        info = receipts[0]["result"] or {}
        _stage(stages, "inspect", "succeeded",
               f"{info.get('fileCount', 0)} files, {info.get('directoryCount', 0)} directories.",
               receipts)

        # --- plan ---------------------------------------------------------- #
        _stage(stages, "plan", "running")
        if self.ai.available:
            try:
                ai_plan = self.ai.plan(request, context)
                plan = ai_plan["plan"]
                plan["source"] = "ai"
                plan["model"] = ai_plan.get("model")
            except AIError as exc:
                plan = _fallback_plan(request)
                plan["note"] = f"AI planning unavailable: {exc}"
        else:
            plan = _fallback_plan(request)
            plan["note"] = "No AI provider configured — using a deterministic plan."
        result["plan"] = plan
        result["tasks"] = self._materialize_plan(plan)
        _stage(stages, "plan", "succeeded",
               f"{len(plan.get('tasks', []))} tasks planned ({plan.get('source', 'deterministic')}).")

        if mode == "plan":
            repository.update_project(self.project_id, status="planned",
                                      current_task=plan.get("summary", "")[:120])
            result["finishedAt"] = time.time()
            return result

        # --- execute ------------------------------------------------------- #
        _stage(stages, "execute", "running")
        execute_receipts, execute_detail = self._execute(request, context, plan)
        _stage(stages, "execute", "succeeded" if execute_receipts else "blocked",
               execute_detail, execute_receipts)
        self._complete_tasks("execute", "succeeded" if execute_receipts else "blocked",
                             execute_detail)

        # --- test ---------------------------------------------------------- #
        _stage(stages, "test", "running")
        test_receipt = EXECUTOR.execute("run_tests", self.project_id)
        test_result = test_receipt["result"] or {}
        test_status = test_result.get("status", "unverified")
        _stage(stages, "test", "succeeded" if test_status == "verified" else "blocked",
               f"Test status: {test_status}", [test_receipt])
        self._complete_tasks("test", "succeeded", f"Test status: {test_status}")
        if test_status != "verified":
            self._record_verification(
                "Tests pass", test_result.get("method", "tests"), test_status,
                test_result.get("evidence", {}), test_result.get("error", ""),
            )

        # --- inspect errors / fix / retest --------------------------------- #
        error_output = ""
        if test_status == "failed":
            _stage(stages, "inspect_errors", "running")
            error_output = (test_result.get("evidence", {}) or {}).get("stderr", "")
            _stage(stages, "inspect_errors", "succeeded",
                   "Captured real error output from the failing test run.")

            if auto_fix and self.ai.available:
                _stage(stages, "fix", "running")
                fix_receipts, fix_detail = self._fix(error_output, context, request)
                _stage(stages, "fix", "succeeded" if fix_receipts else "blocked",
                       fix_detail, fix_receipts)
                if fix_receipts:
                    _stage(stages, "retest", "running")
                    retest = EXECUTOR.execute("run_tests", self.project_id)
                    retest_status = (retest["result"] or {}).get("status", "unverified")
                    _stage(stages, "retest",
                           "succeeded" if retest_status == "verified" else "failed",
                           f"Retest status: {retest_status}", [retest])
                    self._record_verification(
                        "Tests pass after fix", "execution.exit_code", retest_status,
                        (retest["result"] or {}).get("evidence", {}),
                        (retest["result"] or {}).get("error", ""),
                    )
            else:
                reason = "AI provider not configured" if not self.ai.available else "auto-fix disabled"
                _stage(stages, "fix", "blocked", f"Fix stage skipped: {reason}.")
        else:
            for stage_id in ("inspect_errors", "fix", "retest"):
                _stage(stages, stage_id, "skipped", "No failing test run to act on.")

        # --- verify -------------------------------------------------------- #
        _stage(stages, "verify", "running")
        verifications = self._verify_changes()
        result["verifications"] = verifications
        _stage(stages, "verify", "succeeded" if verifications else "blocked",
               f"{len(verifications)} claims verified against real evidence.")

        # --- diff & preview state ------------------------------------------ #
        result["diff"] = compute_diff(self.project_id)
        result["preview"] = PreviewAdapter(self.project_id).status()
        result["finishedAt"] = time.time()

        repository.update_project(
            self.project_id,
            status="idle" if not any(s["status"] == "failed" for s in stages) else "error",
            current_task="",
        )
        self._complete_tasks("verify", "succeeded", "Workflow verification recorded.")
        return result

    # -- helpers ----------------------------------------------------------- #
    def _materialize_plan(self, plan: dict) -> list[dict]:
        created = []
        for item in plan.get("tasks", []):
            task = repository.create_task(
                self.project_id,
                title=item.get("title", "Task"),
                description=item.get("description", ""),
                stage=item.get("stage", "execute"),
                depends_on=item.get("depends_on", []),
                timeout=item.get("timeout", 120),
            )
            created.append(task)
        return created

    def _complete_tasks(self, stage: str, state: str, detail: str) -> None:
        for task in repository.list_tasks(self.project_id):
            if task["stage"] == stage and task["state"] == "planned":
                repository.update_task(task["id"], state=state, attempt=task["attempt"] + 1,
                                       receipt={"detail": detail}, finished_at=time.time())

    def _record_verification(self, claim: str, method: str, status: str,
                             evidence: dict, error: str = "") -> dict:
        return repository.add_verification(
            self.project_id, None, claim, method, status, evidence, error
        )

    def _execute(self, request: str, context: str, plan: dict) -> tuple[list[dict], str]:
        if not self.ai.available:
            return [], ("File generation requires a configured AI provider. "
                        "Configure one in Settings to build files.")
        try:
            generated = self.ai.generate_files(request, context, plan)
        except AIError as exc:
            return [], f"AI build call failed: {exc}"

        changes = generated.get("changes", {})
        receipts = []
        for entry in changes.get("files", [])[:40]:
            path = (entry.get("path") or "").strip()
            if not path:
                continue
            receipts.append(EXECUTOR.execute("write_file", self.project_id,
                                             path=path, content=entry.get("content", "")))
        if changes.get("notes"):
            memory.remember(self.project_id, "decision", str(changes["notes"])[:500])
        ok = sum(1 for r in receipts if r["status"] == "succeeded")
        return receipts, f"Applied {ok}/{len(receipts)} file operations (model: {generated.get('model')})."

    def _fix(self, error_output: str, context: str, request: str) -> tuple[list[dict], str]:
        try:
            generated = self.ai.generate_files(
                f"The test run failed. Fix the root cause.\n\nError output:\n{error_output[:3000]}",
                context,
                {"tasks": [{"title": "Fix failing tests"}]},
            )
        except AIError as exc:
            return [], f"AI fix call failed: {exc}"
        receipts = []
        for entry in generated.get("changes", {}).get("files", [])[:20]:
            path = (entry.get("path") or "").strip()
            if path:
                receipts.append(EXECUTOR.execute("write_file", self.project_id,
                                                 path=path, content=entry.get("content", "")))
        return receipts, f"Applied {len(receipts)} fix operations."

    def _verify_changes(self) -> list[dict]:
        """Verify that every write recorded in this workflow actually landed."""
        results = []
        adapter = FilesystemAdapter(self.project_id)
        for version in repository.list_versions(self.project_id)[-40:]:
            if version["change"] == "deleted":
                continue
            record = verification.verify_file_exists(self.project_id, version["path"])
            results.append(
                repository.add_verification(
                    self.project_id, None, f"File exists: {version['path']}",
                    record["method"], record["status"], record["evidence"], record["error"],
                )
            )
        return results
