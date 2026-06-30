"""Product-level acceptance tests (honesty + reproducibility contract).

These guard the project-level promises: real links, matching provenance, correct
physics, and no overclaimed physics/fabrication status.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from textlayout import build_default_workflow
from textlayout.backend import create_app
from textlayout.schemas.dsl import LayoutSpec

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "examples" / "benchmarks"
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _benchmark_dirs() -> list[Path]:
    return sorted(p for p in BENCH.iterdir() if p.is_dir())


def _verifications() -> list[tuple[str, dict]]:
    out = []
    for folder in _benchmark_dirs():
        vp = folder / "verification.json"
        if vp.is_file():
            out.append((folder.name, json.loads(vp.read_text(encoding="utf-8"))))
    return out


# 1. README benchmark links exist.
def test_readme_benchmark_links_exist() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    targets = {t.split("#")[0] for t in LINK_RE.findall(readme) if t.startswith("examples/benchmarks/")}
    assert targets, "expected benchmark links in README"
    missing = [t for t in targets if not (REPO / t).exists()]
    assert not missing, f"README links to missing paths: {missing}"


# 2. Benchmark images match generated layout provenance.
def test_benchmark_provenance_matches_layout() -> None:
    checked = 0
    for folder in _benchmark_dirs():
        out_json = folder / "output.json"
        layout = folder / "layout.json"
        if not (out_json.is_file() and layout.is_file()):
            continue
        data = json.loads(out_json.read_text(encoding="utf-8"))
        provenance = data.get("provenance")
        if not provenance:
            continue
        sha = hashlib.sha256(layout.read_bytes()).hexdigest()
        assert provenance["layout_json_sha256"] == sha, f"{folder.name}: stale output vs layout"
        checked += 1
    assert checked >= 1, "expected at least one benchmark with provenance"


# 3. 5 MHz LC calculation is numerically correct.
def test_5mhz_lc_physics() -> None:
    lc = 1.0 / (2 * math.pi * 5e6) ** 2
    assert lc == pytest.approx(1.013e-15, rel=1e-3)
    # L = 10 nH, C = 100 pF resonates near 159 MHz, NOT 5 MHz.
    f0 = 1.0 / (2 * math.pi * math.sqrt(10e-9 * 100e-12))
    assert f0 == pytest.approx(159e6, rel=1e-2)
    # Required L for C = 100 pF at 5 MHz is ~10.13 uH (not nH).
    required_l = lc / 100e-12
    assert required_l == pytest.approx(10.13e-6, rel=1e-2)


# 4. No benchmark claims physics_verified unless a solver executed.
def test_no_physics_verified_without_solver() -> None:
    for name, v in _verifications():
        physics = v.get("physics_verification", {})
        if physics.get("physics_verified"):
            assert v.get("simulation_evidence", {}).get("solver_executed") is True, (
                f"{name}: physics_verified without solver_executed"
            )


# 5. No benchmark claims fabrication_ready.
def test_no_fabrication_ready() -> None:
    for name, v in _verifications():
        assert v.get("fabrication_readiness", {}).get("fabrication_ready") is not True, (
            f"{name}: must not claim fabrication_ready"
        )


# 6. IDC verification separates geometry pass from physics pending.
def test_idc_separates_geometry_from_physics() -> None:
    v = json.loads((BENCH / "01_idc_0p6pf" / "verification.json").read_text(encoding="utf-8"))
    assert v["geometry_verification"]["status"] == "pass"
    assert v["physics_verification"]["status"] == "pending"
    assert v["physics_verification"]["physics_verified"] is False


# 7. API exposes a valid OpenAPI schema.
def test_api_openapi_valid() -> None:
    spec = create_app().openapi()
    assert spec["openapi"].startswith("3.")
    assert "/health" in spec["paths"]
    assert "/layout/generate" in spec["paths"]


# 8. Plugin manifest points to a schema reachable in the local server.
def test_plugin_manifest_points_to_reachable_schema() -> None:
    manifest = json.loads((REPO / "docs" / "plugin_manifest.example.json").read_text(encoding="utf-8"))
    url = manifest["api"]["url"]
    assert url.endswith("/openapi.json")
    client = TestClient(create_app())
    assert client.get("/openapi.json").status_code == 200


# 9. `textlayout generate` produces all expected artifacts.
def test_generate_produces_all_artifacts(tmp_path: Path) -> None:
    spec = LayoutSpec.model_validate(
        json.loads((BENCH / "01_idc_0p6pf" / "layout.json").read_text(encoding="utf-8"))
    )
    result = build_default_workflow().run(
        spec, formats=("gds", "svg", "json"), output_dir=tmp_path, stem="idc"
    )
    assert result.report.passed
    for fmt in ("gds", "svg", "json"):
        assert Path(result.files[fmt]).is_file()
        assert Path(result.files[fmt]).stat().st_size > 0


# 10. Failed verification does not export final geometry artifacts.
def test_failed_verification_blocks_export(tmp_path: Path) -> None:
    spec = LayoutSpec(
        component="IDC",
        parameters={
            "finger_pairs": 22,
            "finger_width_um": 4.0,
            "gap_um": 1.0,  # below M1 min spacing (2.0) -> verification fails
            "overlap_um": 250.0,
            "bus_width_um": 25.0,
            "metal_layer": "M1",
        },
    )
    result = build_default_workflow().run(spec, formats=("gds", "svg", "json"), output_dir=tmp_path)
    assert not result.report.passed
    assert not result.files, "no final artifacts may be exported when verification fails"
    assert not list(tmp_path.glob("*.gds"))
