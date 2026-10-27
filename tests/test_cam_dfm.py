from pathlib import Path

from pcb_forge.integrations.cam_preflight import validate_package


def _gerber(path: Path, body: str = "") -> None:
    path.write_text(
        "%TF.GenerationSoftware,KiCad,Pcbnew,9.0*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n"
        "D10*\nX100000Y100000D02*\nX200000Y100000D01*\n"
        + body + "M02*\n",
        encoding="ascii",
    )


def _package(tmp_path: Path) -> Path:
    _gerber(tmp_path / "demo-F_Cu.gtl")
    _gerber(tmp_path / "demo-B_Cu.gbl")
    _gerber(tmp_path / "demo-F_Mask.gts")
    _gerber(tmp_path / "demo-B_Mask.gbs")
    _gerber(tmp_path / "demo-F_Silkscreen.gto")
    (tmp_path / "demo-Edge_Cuts.gm1").write_text(
        "%TF.GenerationSoftware,KiCad,Pcbnew,9.0*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\nD10*\n"
        "X20000000Y-20000000D02*\n"
        "X155000000Y-20000000D01*\n"
        "X155000000Y-100000000D01*\n"
        "X20000000Y-100000000D01*\n"
        "X20000000Y-20000000D01*\nM02*\n",
        encoding="ascii",
    )
    (tmp_path / "demo.drl").write_text(
        "M48\n; metric drill\nMETRIC\nT1C0.800\n%\nG90\nT1\n"
        "X35.0Y-35.0\nM30\n",
        encoding="ascii",
    )
    (tmp_path / "demo-job.gbrjob").write_text(
        '{"FilesAttributes":['
        '{"FileFunction":"Copper,L1,Top"},'
        '{"FileFunction":"Copper,L2,Bot"},'
        '{"FileFunction":"SolderMask,Top"},'
        '{"FileFunction":"SolderMask,Bot"},'
        '{"FileFunction":"Legend,Top"},'
        '{"FileFunction":"Profile"}]}',
        encoding="utf-8",
    )
    return tmp_path


def test_structural_cam_preflight_passes_complete_package(tmp_path: Path):
    report = validate_package(_package(tmp_path))

    assert report["passed"] is True
    assert report["status"] == "PASS_STRUCTURAL_PREFLIGHT"
    assert not report["blocking_issues"]


def test_structural_cam_preflight_blocks_missing_copper_layer(tmp_path: Path):
    package = _package(tmp_path)
    (package / "demo-B_Cu.gbl").unlink()

    report = validate_package(package)

    assert report["passed"] is False
    assert any("Missing required Gerber layer: B.Cu" in item for item in report["blocking_issues"])


def test_structural_cam_preflight_blocks_invalid_drill_file(tmp_path: Path):
    package = _package(tmp_path)
    (package / "demo.drl").write_text("not an Excellon file", encoding="ascii")

    report = validate_package(package)

    assert report["passed"] is False
    assert any("Excellon header M48 is missing" in item for item in report["blocking_issues"])
    assert any("No drill coordinates found" in item for item in report["blocking_issues"])


def test_structural_cam_preflight_blocks_unclosed_outline(tmp_path: Path):
    package = _package(tmp_path)
    edge = package / "demo-Edge_Cuts.gm1"
    edge.write_text(
        "%TF.GenerationSoftware,KiCad,Pcbnew,9.0*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\nD10*\n"
        "X20000000Y-20000000D02*\n"
        "X155000000Y-20000000D01*\n"
        "X155000000Y-100000000D01*\n"
        "X20000000Y-100000000D01*\n"
        "X20000000Y-30000000D01*\nM02*\n",
        encoding="ascii",
    )

    report = validate_package(package)

    assert report["passed"] is False
    assert any("does not close" in item for item in report["blocking_issues"])
