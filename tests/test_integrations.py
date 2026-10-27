from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from pcb_forge.integrations.circuit_synth import (
    IntegrationUnavailable,
    generate,
    generate_from_source,
)
from pcb_forge.integrations.kicad_cli import validate_project
from pcb_forge.integrations.manufacturing import export_manufacturing


def test_circuit_synth_writes_request_and_uses_argument_list(tmp_path: Path):
    completed = CompletedProcess(args=["adapter"], returncode=0, stdout="ok", stderr="")
    with patch("pcb_forge.integrations.circuit_synth.subprocess.run", return_value=completed) as run:
        result = generate(tmp_path, "  Make a 5V regulator  ", "trusted-wrapper", 30)

    request_file = tmp_path / "design_request.txt"
    assert request_file.read_text(encoding="utf-8") == "Make a 5V regulator\n"
    assert result["returncode"] == 0
    assert result["adapter_contract"] == "external-wrapper-v1"
    args, kwargs = run.call_args
    assert args[0][0] == "trusted-wrapper"
    assert args[0][-4:] == [
        "--request-file",
        str(request_file),
        "--output-dir",
        str(tmp_path),
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 30


def test_generation_requires_configured_wrapper(tmp_path: Path):
    with pytest.raises(IntegrationUnavailable, match="trusted wrapper"):
        generate(tmp_path, "A sufficiently detailed circuit request", "")


def test_kicad_validation_reports_missing_board_and_schematic(tmp_path: Path):
    report = validate_project(tmp_path, "kicad-cli")

    assert report.passed is False
    assert {item.code for item in report.diagnostics} >= {"PCB_MISSING", "SCHEMATIC_MISSING"}


def test_kicad_validation_passes_when_erc_and_drc_succeed(tmp_path: Path):
    (tmp_path / "demo.kicad_pcb").write_text("board", encoding="utf-8")
    (tmp_path / "demo.kicad_sch").write_text("schematic", encoding="utf-8")
    completed = CompletedProcess(args=["kicad-cli"], returncode=0, stdout="", stderr="")

    with patch("pcb_forge.integrations.kicad_cli.run_cli", return_value=completed) as run:
        report = validate_project(tmp_path, "kicad-cli")

    assert report.passed is True
    assert report.checks_run == ["DRC:demo.kicad_pcb", "ERC:demo.kicad_sch"]
    assert run.call_count == 2


def test_manufacturing_export_runs_gerber_drill_and_step(tmp_path: Path):
    board = tmp_path / "demo.kicad_pcb"
    board.write_text("board", encoding="utf-8")
    completed = CompletedProcess(args=["kicad-cli"], returncode=0, stdout="", stderr="")

    def fake_run(_cli, args, _cwd, _timeout):
        if args[1:3] == ["export", "gerbers"]:
            out_dir = Path(args[args.index("-o") + 1])
            (out_dir / "demo-F_Cu.gbr").write_text("gerber", encoding="utf-8")
        elif args[1:3] == ["export", "drill"]:
            out_dir = Path(args[args.index("-o") + 1])
            (out_dir / "demo-PTH.drl").write_text("drill", encoding="utf-8")
        elif args[1:3] == ["export", "step"]:
            step_file = Path(args[args.index("-o") + 1])
            step_file.write_text("step", encoding="utf-8")
        return completed

    with patch("pcb_forge.integrations.manufacturing.run_cli", side_effect=fake_run) as run:
        result = export_manufacturing(tmp_path, "kicad-cli")

    assert result["ok"] is True
    assert len(result["commands_run"]) == 3
    assert {Path(path).suffix for path in result["outputs"]} >= {".gbr", ".drl", ".step"}
    assert run.call_count == 3


def test_manufacturing_export_stops_after_cli_failure(tmp_path: Path):
    (tmp_path / "demo.kicad_pcb").write_text("board", encoding="utf-8")
    failed = CompletedProcess(args=["kicad-cli"], returncode=1, stdout="", stderr="export failed")

    with patch("pcb_forge.integrations.manufacturing.run_cli", return_value=failed) as run:
        result = export_manufacturing(tmp_path, "kicad-cli")

    assert result["ok"] is False
    assert "export failed" in result["error"]
    assert run.call_count == 1


def test_manufacturing_export_requires_board(tmp_path: Path):
    result = export_manufacturing(tmp_path, "kicad-cli")

    assert result["ok"] is False
    assert result["outputs"] == []



def test_native_circuit_synth_backend_runs_reviewed_module_in_subprocess(tmp_path: Path):
    source = tmp_path / "design.py"
    source.write_text("def build_circuit(): pass\\n", encoding="utf-8")
    (tmp_path / "demo.kicad_pcb").write_text("board", encoding="utf-8")
    completed = CompletedProcess(
        args=["python"], returncode=0, stdout="generated", stderr=""
    )

    with patch(
        "pcb_forge.integrations.circuit_synth.subprocess.run", return_value=completed
    ) as run:
        result = generate_from_source(tmp_path, source, timeout=45)

    assert result["ok"] is True
    assert result["adapter_contract"] == "circuit-synth-python-module-v1"
    args, kwargs = run.call_args
    assert args[0][1].endswith("circuit_synth_runner.py")
    assert args[0][2] == str(source)
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 45


def test_native_circuit_synth_backend_rejects_source_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external_source = tmp_path / "untrusted.py"
    external_source.write_text("print('not run')\\n", encoding="utf-8")

    with pytest.raises(IntegrationUnavailable, match="inside the project workspace"):
        generate_from_source(workspace, external_source)
