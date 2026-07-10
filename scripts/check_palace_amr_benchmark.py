"""Rebuild and audit the quarter-wave Palace AMR verification report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.simulation.palace_backend import parse_eigenmodes  # noqa: E402
from textlayout.simulation.palace_verification import (  # noqa: E402
    PalaceAMRLevel,
    PalaceVerificationStudy,
    assess_palace_verification,
    parse_domain_field_participation,
    sha256_file,
    write_report,
)

BENCHMARK = ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave"
MANIFEST = BENCHMARK / "mesh_manifest.json"
REPORT = BENCHMARK / "evidence" / "amr_verification.json"


def build_study() -> PalaceVerificationStudy:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    levels: list[PalaceAMRLevel] = []
    for raw in manifest["levels"]:
        eig_path = BENCHMARK / raw["eig_csv"]
        energy_path = BENCHMARK / raw["domain_energy_csv"]
        mode = parse_eigenmodes(eig_path)[0]
        electric, magnetic, energy_error = parse_domain_field_participation(
            energy_path, mode=mode.index, region_names={1: "substrate_bulk", 2: "vacuum"}
        )
        levels.append(
            PalaceAMRLevel(
                tag=raw["tag"],
                refinement_kind="uniform_unstructured",
                polynomial_order=manifest["solver"]["element_order"],
                frequency_ghz=mode.frequency_ghz,
                energy_normalization_error_percent=energy_error,
                electric_energy_by_region=electric,
                magnetic_energy_by_region=magnetic,
                participation_by_region=electric,
                output_file_hashes={
                    raw["eig_csv"]: sha256_file(eig_path),
                    raw["domain_energy_csv"]: sha256_file(energy_path),
                },
            )
        )
    return PalaceVerificationStudy(
        design_id="palace_cpw_quarter_wave",
        solver_version=manifest["solver"]["version"],
        solver_artifact_hash=manifest["solver"]["container_digest"],
        levels=levels,
        sweeps=[],
        independent_reference=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="update the committed report")
    parser.add_argument(
        "--require-verified", action="store_true", help="fail unless every physics gate passes"
    )
    args = parser.parse_args(argv)
    report = assess_palace_verification(build_study())
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=False) + "\n"
    if args.write:
        write_report(report, REPORT)
    elif not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != rendered:
        print(f"Palace AMR report drift: run {Path(__file__).name} --write")
        return 1
    print(
        f"Palace AMR benchmark: {report.status.value}; "
        f"{len(report.blockers)} blocking gate(s)"
    )
    for blocker in report.blockers:
        print(f"  BLOCKED: {blocker}")
    if args.require_verified and not report.verified:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
