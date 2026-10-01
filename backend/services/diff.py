"""Diff system — real change tracking derived from stored file versions."""
from __future__ import annotations

import difflib

from .. import repository


def compute_diff(project_id: str) -> dict:
    versions = repository.list_versions(project_id)
    latest: dict[str, dict] = {}
    for version in versions:
        latest[version["path"]] = version

    files = []
    total_additions = 0
    total_deletions = 0

    for path, version in latest.items():
        rows = repository.list_versions(project_id, path)
        previous_content = ""
        for row in reversed(rows):
            if row["id"] != version["id"]:
                previous_content = row["content"]
                break

        change = version["change"]
        current = repository.get_file(project_id, path)
        current_content = current["content"] if current else version["content"]

        if change == "deleted":
            current_content = ""
        if change == "added":
            previous_content = ""

        diff_lines = list(
            difflib.unified_diff(
                previous_content.splitlines(),
                current_content.splitlines(),
                fromfile=f"a/{path}" if change != "added" else "/dev/null",
                tofile=f"b/{path}" if change != "deleted" else "/dev/null",
                lineterm="",
            )
        )
        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        total_additions += additions
        total_deletions += deletions

        files.append(
            {
                "path": path,
                "change": change,
                "additions": additions,
                "deletions": deletions,
                "before": previous_content,
                "after": current_content,
                "diff": "\n".join(diff_lines) or f"(no textual change) {path}",
                "updatedAt": version["created_at"],
            }
        )

    files.sort(key=lambda item: item["updatedAt"], reverse=True)
    return {
        "files": files,
        "changedCount": len(files),
        "additions": total_additions,
        "deletions": total_deletions,
    }
