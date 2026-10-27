import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_circuit_synth_e2e.py"
SPEC = importlib.util.spec_from_file_location("run_circuit_synth_e2e", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load E2E script from {SCRIPT_PATH}")
run_circuit_synth_e2e = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_circuit_synth_e2e
SPEC.loader.exec_module(run_circuit_synth_e2e)


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



def test_manufacturing_gate_blocks_unrouted_fallback():
    gate = run_circuit_synth_e2e._manufacturing_gate(
        [
            {"kind": "ERC", "errors": 0, "warnings": 0},
            {"kind": "DRC", "violations": 0, "unconnected_items": 8},
        ],
        [],
        fallback_used=True,
    )

    assert gate["passed"] is False
    assert gate["ready"] is False
    assert "PCB fallback created an unrouted placement seed" in gate["blocking_reasons"]
    assert "DRC reports 8 unconnected pads" in gate["blocking_reasons"]


def test_manufacturing_gate_passes_only_for_routed_clean_board():
    gate = run_circuit_synth_e2e._manufacturing_gate(
        [
            {"kind": "ERC", "errors": 0, "warnings": 0},
            {"kind": "DRC", "violations": 0, "unconnected_items": 0},
        ],
        [],
        fallback_used=False,
    )

    assert gate["passed"] is True
    assert gate["ready"] is True
    assert gate["blocking_reasons"] == []
