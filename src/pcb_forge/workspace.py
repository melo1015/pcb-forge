"""Workspace creation and path confinement."""

import re

from pathlib import Path


_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class WorkspaceError(ValueError):
    """Raised when a workspace name or path is invalid."""


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, name: str) -> Path:
        if not _NAME_RE.fullmatch(name):
            raise WorkspaceError("Workspace name must use 1-64 letters, digits, '_' or '-'.")
        target = (self.root / name).resolve()
        if not target.is_relative_to(self.root):
            raise WorkspaceError("Workspace path escapes configured root.")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def resolve_project(self, name: str) -> Path:
        if not _NAME_RE.fullmatch(name):
            raise WorkspaceError("Invalid project name.")
        target = (self.root / name).resolve()
        if not target.is_relative_to(self.root) or not target.is_dir():
            raise WorkspaceError("Project does not exist inside configured workspace.")
        return target
