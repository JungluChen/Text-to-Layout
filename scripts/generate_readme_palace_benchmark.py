"""Generate the README "Tested Palace 0.17 benchmark" subsection from evidence.

    uv run python scripts/generate_readme_palace_benchmark.py [--check]

The subsection between the palace-v017-benchmark markers is rendered ONLY
from the committed benchmark packet under
``examples/solver_benchmarks/palace_cpw_quarter_wave_v017/``. ``--check``
fails when the README text drifts from what the committed evidence supports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.canonical import load_canonical  # noqa: E402

README = ROOT / "README.md"
PACKET = ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave_v017"
BEGIN = "<!-- BEGIN GENERATED: palace-v017-benchmark -->"
END = "<!-- END GENERATED: palace-v017-benchmark -->"


def render() -> str:
    evidence = load_canonical(PACKET / "canonical_evidence.json")
    manifest = json.loads((PACKET / "run_manifest.json").read_text(encoding="utf-8"))
    toolchain = json.loads((PACKET / "toolchain.json").read_text(encoding="utf-8"))
    convergence = json.loads((PACKET / "convergence.json").read_text(encoding="utf-8"))
    environment = json.loads((PACKET / "test_environment.json").read_text(encoding="utf-8"))
    amr = manifest["amr"]
    initial = manifest["initial_mesh"]
    numerical = convergence["verification_report"]["numerical_domain_results"]
    worst = max(
        (
            r["frequency_sensitivity_percent"]
            for r in numerical
            if r["frequency_sensitivity_percent"] is not None
        ),
        default=None,
    )
    gmsh_version = toolchain["gmsh"].get("version", "unknown")
    executable_prefix = str(evidence.solver_executable_sha256 or "")[:16]
    resonator_runtime = sum(
        inv["runtime_seconds"] for inv in manifest["invocations"]
    )
    lines = [
        "#### Tested Palace 0.17 benchmark",
        "",
        "Generated from committed canonical evidence in "
        "[examples/solver_benchmarks/palace_cpw_quarter_wave_v017/]"
        "(examples/solver_benchmarks/palace_cpw_quarter_wave_v017/) — do not edit by hand "
        "(`scripts/generate_readme_palace_benchmark.py`).",
        "",
        "| | |",
        "|---|---|",
        f"| Test date | {evidence.timestamp} |",
        f"| Git commit | `{evidence.git_commit}` |",
        f"| Palace | `{evidence.solver_version}` (executable SHA-256 "
        f"`{executable_prefix}…`) |",
        f"| Gmsh | `{gmsh_version}` |",
        f"| Tested OS | {environment['os']}; {environment['wsl']} |",
        f"| CPU / RAM | {environment['cpu']}; {environment['ram']} |",
        f"| Installation | {environment['install_duration']} |",
        f"| Smoke test | {environment['smoke_runtime']} |",
        f"| Resonator benchmark | {resonator_runtime:.0f} s total Palace wall time |",
        f"| AMR iterations | {amr['accepted_iterations']} accepted "
        f"({amr['stop_reason']}) |",
        f"| Elements | {initial['element_count']} → {amr['final_element_count']} |",
        f"| ND DOF (final) | {amr['final_degrees_of_freedom']} |",
        f"| Tracked frequency | `{evidence.extracted_value}` GHz |",
        f"| Final global error indicator | "
        f"{amr['final_global_error_indicator_percent']:.4f}% |",
        (
            f"| Worst numerical-domain frequency sensitivity | {worst:.4f}% |"
            if worst is not None
            else "| Worst numerical-domain frequency sensitivity | not assessed |"
        ),
        f"| Evidence status | **`{evidence.status.value}`** |",
        "",
        "Palace and Gmsh remain optional external tools and are not bundled in the "
        "wheel. A successful solver process is not automatically physics "
        "verification: this run has no independent reference artifact and is "
        "therefore limited to `SIMULATION_EXECUTED` even though its numerical "
        "gates converged. Physical sensitivity (substrate thickness, "
        "permittivity) is reported separately in the benchmark packet and is "
        "not the same as numerical convergence.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    readme = README.read_text(encoding="utf-8")
    if not PACKET.is_dir() or not (PACKET / "canonical_evidence.json").is_file():
        print("no committed Palace 0.17 packet; README subsection is not required")
        return 0
    section = f"{BEGIN}\n\n{render()}\n\n{END}"
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    if pattern.search(readme):
        updated = pattern.sub(lambda _match: section, readme)
    else:
        anchor = "## Run the doctor"
        if anchor not in readme:
            print("[FAIL] README anchor for the generated subsection is missing")
            return 1
        updated = readme.replace(anchor, f"{section}\n\n{anchor}", 1)
    if args.check:
        if readme != updated:
            print(
                "[FAIL] README Tested Palace 0.17 benchmark subsection drifted from "
                "the committed evidence; rerun scripts/generate_readme_palace_benchmark.py",
                file=sys.stderr,
            )
            return 1
        print("README Palace 0.17 benchmark subsection is current")
        return 0
    README.write_text(updated, encoding="utf-8", newline="\n")
    print("README Palace 0.17 benchmark subsection regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
