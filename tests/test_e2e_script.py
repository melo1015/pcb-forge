import json
import sys
from pathlib import Path

from scripts import run_circuit_synth_e2e


def _prepare(monkeypatch, tmp_path: Path, result: dict) -> Path:
    source = tmp_path / "design.py"
    source.write_text("def build_circuit(): pass\n", encoding="utf-8")
    output = tmp_path / "artifacts"
    monkeypatch.setattr(run_circuit_synth_e2e.shutil, "which", lambda _name: "/usr/bin/kicad-cli")
    monkeypatch.setattr(
        run_circuit_synth_e2e,
        "generate_from_source",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_circuit_synth_e2e.py", str(source), "--output-dir", str(output)],
    )
    return output


def test_missing_kicad_outputs_writes_valid_summary_with_newline(monkeypatch, tmp_path):
    output = _prepare(monkeypatch, tmp_path, {"ok": True, "project": "generated"})

    assert run_circuit_synth_e2e.main() == 1

    summary_path = output / "e2e-summary.json"
    raw = summary_path.read_bytes()
    summary = json.loads(raw)
    assert raw.endswith(b"\n")
    assert summary["generation"]["ok"] is True
    assert summary["schematics"] == []
    assert summary["boards"] == []
    assert summary["validation_commands"] == []
    assert "missing" in summary["note"]


def test_generation_failure_writes_summary(monkeypatch, tmp_path):
    output = _prepare(monkeypatch, tmp_path, {"ok": False, "error": "generator failed"})

    assert run_circuit_synth_e2e.main() == 1

    summary = json.loads((output / "e2e-summary.json").read_text(encoding="utf-8"))
    assert summary["generation"]["error"] == "generator failed"
    assert summary["validation_commands"] == []
    assert summary["note"] == "Generation failed; ERC/DRC were not run."
