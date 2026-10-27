from pathlib import Path

import pytest

from pcb_forge.workspace import Workspace, WorkspaceError


def test_create_and_resolve(tmp_path: Path):
    workspace = Workspace(tmp_path / "work")
    created = workspace.create("sensor_board")
    assert created.is_dir()
    assert workspace.resolve_project("sensor_board") == created


@pytest.mark.parametrize("name", ["../escape", "", "a/b", ".hidden", "bad name"])
def test_reject_unsafe_names(tmp_path: Path, name: str):
    workspace = Workspace(tmp_path / "work")
    with pytest.raises(WorkspaceError):
        workspace.create(name)


def test_resolve_requires_existing_directory(tmp_path: Path):
    workspace = Workspace(tmp_path / "work")
    with pytest.raises(WorkspaceError):
        workspace.resolve_project("missing")
