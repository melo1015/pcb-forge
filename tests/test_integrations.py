from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pcb_forge.integrations.circuit_synth import generate
from pcb_forge.integrations.kicad_cli import validate_project


def test_circuit_synth_writes_request_and_uses_argument_list(tmp_path: Path):
    completed = CompletedProcess(args=["circuit-synth"], returncode=0, stdout="ok", stderr="")
    with patch("pcb_forge.integrations.circuit_synth.subprocess.run", return_value=completed) as run:
        result = generate(tmp_path, "  Make a 5V regulator  ", "circuit-synth", 30)

    request_file = tmp_path / "design_request.txt"
    assert request_file.read_text(encoding="utf-8") == "Make a 5V regulator\n"
    assert result["returncode"] == 0
    args, kwargs = run.call_args
    assert args[0][0] == "circuit-synth"
    assert args[0][-4:] == [
        "--request-file",
        str(request_file),
        "--output-dir",
        str(tmp_path),
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 30


def test_circuit_synth_requires_configured_command(tmp_path: Path):
    import pytest

    from pcb_forge.integrations.circuit_synth import IntegrationUnavailable

    with pytest.raises(IntegrationUnavailable):
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
