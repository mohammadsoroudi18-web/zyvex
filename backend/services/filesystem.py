"""FilesystemAdapter — a clean filesystem abstraction backed by project data.

The database is the source of truth. `materialize()` writes a project to a real
temporary directory so the ExecutionAdapter can run real commands against it.
This keeps a single source of truth while still enabling genuine execution.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .. import repository

WORKSPACE_ROOT = Path(tempfile.gettempdir()) / "nexora-workspaces"


class FilesystemAdapter:
    def __init__(self, project_id: str):
        self.project_id = project_id

    # -- reads ------------------------------------------------------------- #
    def list(self) -> list[dict]:
        return repository.list_files(self.project_id)

    def read(self, path: str) -> str | None:
        row = repository.get_file(self.project_id, path)
        return None if row is None else row["content"]

    def exists(self, path: str) -> bool:
        return repository.get_file(self.project_id, path) is not None

    def tree(self) -> list[dict]:
        files = repository.list_files(self.project_id)
        return [
            {
                "path": row["path"],
                "name": row["name"],
                "isDir": bool(row["is_dir"]),
                "language": row["language"],
                "updatedAt": row["updated_at"],
                "size": len(row["content"] or ""),
            }
            for row in files
        ]

    def search(self, term: str, content: bool = False) -> list[dict]:
        return repository.search_files(self.project_id, term, content_search=content)

    # -- writes ------------------------------------------------------------ #
    def create(self, path: str, content: str = "", is_dir: bool = False) -> dict:
        return repository.create_file(self.project_id, path, content, is_dir)

    def write(self, path: str, content: str) -> dict:
        return repository.write_file(self.project_id, path, content)

    def edit(self, path: str, find: str, replace: str) -> dict:
        row = repository.get_file(self.project_id, path)
        if row is None:
            raise FileNotFoundError(f"{path} does not exist")
        if find not in (row["content"] or ""):
            raise ValueError(f"search text not found in {path}")
        return repository.write_file(self.project_id, path, row["content"].replace(find, replace))

    def delete(self, path: str) -> int:
        return repository.delete_file(self.project_id, path)

    def rename(self, path: str, new_path: str) -> dict | None:
        return repository.rename_file(self.project_id, path, new_path)

    def create_directory(self, path: str) -> dict:
        return repository.create_file(self.project_id, path, "", is_dir=True)

    # -- materialization for execution ------------------------------------- #
    def materialize(self) -> Path:
        target = WORKSPACE_ROOT / self.project_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
        for row in self.list():
            if row["is_dir"]:
                continue
            destination = target / row["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(row["content"] or "", encoding="utf-8")
        return target
