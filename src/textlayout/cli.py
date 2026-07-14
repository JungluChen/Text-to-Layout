"""Command-line interface for textlayout.

Four subcommands cover the usage modes from a single shared core:

    textlayout prompt "Create a 0.6 pF IDC ..." --out out/idc_demo  # NL -> closed loop
    textlayout generate spec.json --out out_dir   # DSL file -> verified artifacts
    textlayout verify   spec.json                 # DSL file -> verification report
    textlayout doctor                             # environment + solver health check
    textlayout serve    --host 0.0.0.0 --port 8000  # run the plugin API server
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textlayout import __version__, build_default_workflow, build_from_text_workflow
from textlayout.errors import TextLayoutError
from textlayout.schemas.dsl import LayoutSpec

if TYPE_CHECKING:  # pragma: no cover
    from textlayout.chip_lattice import QubitLattice
    from textlayout.measurement import CalibrationOverlay
    from textlayout.epr import EPRResult
    from textlayout.measurement import MeasurementRecord, SimulatedPrediction


def _load_spec(path: str) -> LayoutSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LayoutSpec.model_validate(data)


def _load_lattice(path: str) -> "QubitLattice":
    from textlayout.chip_lattice import QubitLattice

    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return QubitLattice.model_validate(data)


def _pdk_provenance_payload(technology_name: str) -> dict[str, object]:
    """Every report must record which PDK backed it -- name, version, file
    hash, and calibration status -- or say plainly that none is available.
    """
    from textlayout.pdk import find_pdk_provenance_for_technology

    provenance = find_pdk_provenance_for_technology(technology_name)
    if provenance is None:
        return {
            "available": False,
            "technology": technology_name,
            "note": f"Technology {technology_name!r} is not backed by a PDK YAML "
            "(e.g. the built-in generic_2metal Technology, which predates the "
            "PDK schema). No PDK provenance is available.",
        }
    return {"available": True, **provenance.model_dump(mode="json")}


def _cmd_prompt(args: argparse.Namespace) -> int:
    workflow = build_from_text_workflow()
    result = workflow.run(
        args.prompt,
        args.out,
        tolerance_percent=args.tolerance,
        execute_solver=not args.no_solver,
        solver_executable=args.executable,
    )
    payload = result.to_dict()
    payload["pdk_provenance"] = _pdk_provenance_payload(result.spec.technology)
    if getattr(args, "include_epr", False):
        from textlayout.epr import render_markdown as render_epr_markdown
        from textlayout.epr import write_epr_report

        epr_result = _run_epr(result.spec, frequency_ghz=None)
        payload["epr"] = epr_result.to_dict()
        payload["epr_files"] = write_epr_report(epr_result, args.out)
        report_path = result.files.get("report")
        if report_path:
            _append_epr_section_to_report(Path(report_path), render_epr_markdown(epr_result))
    missing = result.missing_circuit_simulators
    if args.strict_simulation and missing:
        payload["strict_simulation_failure"] = (
            f"requested circuit simulators are not installed: {', '.join(missing)}"
        )
        print(json.dumps(payload, indent=2))
        return 3
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 2


def _cmd_generate(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    spec = _load_spec(args.spec)
    result = workflow.run(spec, output_dir=args.out)
    print(
        json.dumps(
            {
                "summary": result.summary,
                "verification": result.report.to_dict(),
                "files": dict(result.files),
                "pdk_provenance": _pdk_provenance_payload(spec.technology),
            },
            indent=2,
        )
    )
    return 0 if result.report.passed else 2


def _append_epr_section_to_report(report_path: Path, epr_markdown: str) -> None:
    """Fold the EPR/coherence markdown into the main design report as one section.

    Demotes the EPR report's own top-level heading by one level so it nests
    under the design report instead of competing with it, then appends a
    horizontal rule + the demoted section. Never overwrites — the design
    report's capacitance/inductance content is untouched.
    """
    if not report_path.is_file():
        return
    demoted = "\n".join(
        f"#{line}" if line.startswith("#") else line for line in epr_markdown.splitlines()
    )
    existing = report_path.read_text(encoding="utf-8")
    report_path.write_text(existing.rstrip("\n") + "\n\n---\n\n" + demoted, encoding="utf-8")


def _cmd_verify(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    spec = _load_spec(args.spec)
    report = workflow.verify_only(spec)
    payload = report.to_dict()
    payload["pdk_provenance"] = _pdk_provenance_payload(spec.technology)
    if getattr(args, "include_epr", False):
        payload["epr"] = _run_epr(spec, frequency_ghz=args.frequency_ghz).to_dict()
    print(json.dumps(payload, indent=2))
    return 0 if report.passed else 2


def _run_epr(
    spec: LayoutSpec, *, frequency_ghz: float | None, pdk: str | None = None
) -> "EPRResult":
    """Run the default EPR backend with PDK-backed materials and provenance.

    Every EPR result carries the exact PDK file (name, version, sha256,
    calibration status) its material assumptions came from — defaulting to
    ``generic_2metal`` (illustrative, NOT fabrication-ready) when the caller
    does not name one. Using a PDK never changes the honesty status: the
    analytical backend stays EPR_ANALYTICAL_ONLY.
    """
    from textlayout.epr import DEFAULT_PDK_NAME, default_epr_backend, materials_db_from_pdk

    frequency = frequency_ghz
    if frequency is None:
        target = spec.target.get("frequency_ghz")
        frequency = float(target) if isinstance(target, (int, float)) and target > 0 else 6.0
    materials, pdk_provenance = materials_db_from_pdk(pdk or DEFAULT_PDK_NAME)
    result = default_epr_backend().analyze(spec, frequency_ghz=frequency, materials=materials)
    return result.model_copy(update={"pdk_provenance": pdk_provenance.model_dump(mode="json")})


def _cmd_epr(args: argparse.Namespace) -> int:
    from textlayout.epr import EPR_STATUS_SKIPPED, write_epr_report

    spec = _load_spec(args.spec)
    try:
        result = _run_epr(spec, frequency_ghz=args.frequency_ghz, pdk=args.pdk)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_epr_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.status != EPR_STATUS_SKIPPED or not args.strict else 3


def _cmd_yield_jj(args: argparse.Namespace) -> int:
    from textlayout.yield_model import (
        FrequencyTarget,
        JJProcessModel,
        JunctionGeometry,
        run_jj_yield,
        write_yield_report,
    )

    process = JJProcessModel(
        target_jc_ua_per_um2=args.jc,
        wafer_jc_sigma_pct=args.wafer_sigma_pct,
        local_jc_sigma_pct=args.local_sigma_pct,
        cd_sigma_nm=args.cd_sigma_nm,
        junction_area_bias_um2=args.area_bias_um2,
        spatial_gradient_pct_per_mm=args.gradient_pct_per_mm,
    )
    junction = JunctionGeometry(width_um=args.width_um, height_um=args.height_um)
    target = FrequencyTarget(target_ghz=args.target_ghz, tolerance_mhz=args.tolerance_mhz)
    result = run_jj_yield(
        process=process,
        junction=junction,
        shunt_c_pf=args.shunt_c_pf,
        target=target,
        n_samples=args.n_samples,
        seed=args.seed,
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_yield_qubit_array(args: argparse.Namespace) -> int:
    from textlayout.yield_model import (
        FrequencyTarget,
        JJProcessModel,
        JunctionGeometry,
        run_qubit_array_yield,
        write_yield_report,
    )

    process = JJProcessModel(
        target_jc_ua_per_um2=args.jc,
        wafer_jc_sigma_pct=args.wafer_sigma_pct,
        local_jc_sigma_pct=args.local_sigma_pct,
        cd_sigma_nm=args.cd_sigma_nm,
        junction_area_bias_um2=args.area_bias_um2,
        spatial_gradient_pct_per_mm=args.gradient_pct_per_mm,
    )
    junction = JunctionGeometry(width_um=args.width_um, height_um=args.height_um)
    target = FrequencyTarget(target_ghz=args.target_ghz, tolerance_mhz=args.tolerance_mhz)
    result = run_qubit_array_yield(
        process=process,
        junction=junction,
        shunt_c_pf=args.shunt_c_pf,
        target=target,
        n_qubits=args.n_qubits,
        n_chips=args.n_chips,
        qubit_pitch_mm=args.qubit_pitch_mm,
        seed=args.seed,
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_chip_analyze(args: argparse.Namespace) -> int:
    from textlayout.chip_lattice import run_chip_collision_yield, write_chip_yield_report

    lattice = _load_lattice(args.lattice)
    result = run_chip_collision_yield(lattice, n_samples=args.n_samples, seed=args.seed)
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_chip_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.nominal_report.collision_free or not args.strict else 2


def _cmd_chip_optimize(args: argparse.Namespace) -> int:
    from textlayout.chip_lattice import optimize_frequencies, write_chip_optimize_report

    lattice = _load_lattice(args.lattice)
    result = optimize_frequencies(
        lattice, max_retune_mhz=args.max_retune_mhz, step_mhz=args.step_mhz
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_chip_optimize_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.after.collision_free or not args.strict else 2


def _cmd_pdk_list(args: argparse.Namespace) -> int:
    from textlayout import build_default_workflow

    workflow = build_default_workflow()
    print(json.dumps({"technologies": workflow.technology_names}, indent=2))
    return 0


def _cmd_pdk_info(args: argparse.Namespace) -> int:
    from textlayout.knowledge.technology_library import PDKS_DIR
    from textlayout.pdk import load_pdk

    for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
        pdk = load_pdk(pdk_path)
        if pdk.name == args.name:
            payload = pdk.model_dump(mode="json")
            print(json.dumps(payload, indent=2))
            return 0
    print(
        json.dumps(
            {
                "error": "not a PDK-backed technology",
                "message": (
                    f"{args.name!r} is not loaded from a PDK YAML (it may be the "
                    "built-in generic_2metal Technology, which predates the PDK "
                    "schema). No richer PDK metadata is available."
                ),
            }
        ),
        file=sys.stderr,
    )
    return 1


def _load_predictions(path: str) -> "list[SimulatedPrediction]":
    from textlayout.measurement import load_predictions

    return load_predictions(path)


def _load_measurements(path: str) -> "list[MeasurementRecord]":
    from textlayout.measurement import load_measurements

    return load_measurements(path)


def _cmd_measurement_compare(args: argparse.Namespace) -> int:
    from textlayout.measurement import (
        build_comparison_summary,
        compare_all,
        pair_by_design_hash,
        write_comparison_bundle,
        write_comparison_report,
    )

    predictions = _load_predictions(args.predicted)
    measurements = _load_measurements(args.measured)
    pairs = pair_by_design_hash(predictions, measurements)
    residuals = compare_all(pairs)
    summary = build_comparison_summary(
        residuals,
        n_predictions=len(predictions),
        n_measurements=len(measurements),
        n_matched=len(pairs),
        any_synthetic=(not measurements) or any(m.synthetic for m in measurements),
        pdk_names=[p.pdk_name for p in predictions if p.pdk_name],
    )
    payload: dict[str, object] = {
        "summary": summary,
        "residuals": [r.model_dump(mode="json") for r in residuals],
    }
    if args.out:
        files = write_comparison_bundle(residuals, summary, args.out)
        # legacy artifact names kept for compatibility, under distinct keys
        legacy = write_comparison_report(residuals, args.out)
        files["legacy_json"] = legacy["json"]
        files["legacy_markdown"] = legacy["markdown"]
        payload["files"] = files
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_measurement_calibrate(args: argparse.Namespace) -> int:
    from textlayout.epr.pdk_bridge import resolve_pdk_path
    from textlayout.measurement import (
        build_calibration,
        build_overlay,
        write_calibration,
        write_calibration_report,
        write_overlay,
    )

    predictions = _load_predictions(args.predicted)
    measurements = _load_measurements(args.measured)
    calibration = build_calibration(predictions, measurements, synthetic=not args.production)
    base_pdk_path = resolve_pdk_path(args.base_pdk)
    overlay = build_overlay(
        predictions,
        measurements,
        base_pdk_path=base_pdk_path,
        input_files=[args.predicted, args.measured],
        min_samples=args.min_samples,
    )
    if args.production and overlay.is_synthetic:
        print(
            json.dumps(
                {
                    "error": "--production was passed but at least one measurement "
                    "record is marked synthetic; refusing to emit a "
                    "measurement-calibrated overlay from fixture data."
                },
                indent=2,
            )
        )
        return 2
    # The v0.3 payload put the calibration fields (`synthetic`, `corrections`,
    # `n_records`, ...) at the top level. Keep them there and add `overlay`
    # alongside, so existing consumers of `textlayout measurement calibrate`
    # keep working. See docs/deprecation_policy.md.
    payload: dict[str, object] = dict(calibration.to_dict())
    payload["overlay"] = overlay.to_dict()
    if args.out:
        out = Path(args.out)
        files = {
            "calibration": str(write_calibration(calibration, out / "calibration.yaml")),
            "overlay": str(write_overlay(overlay, out / "calibrated_pdk_overlay.yaml")),
        }
        files.update(write_calibration_report(calibration, args.out))
        report = {
            "schema": "textlayout.measurement-calibration-report.v1",
            "overlay": overlay.to_dict(),
            "legacy_calibration": calibration.to_dict(),
        }
        json_path = out / "measurement_calibration_report.json"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        md_path = out / "measurement_calibration_report.md"
        md_path.write_text(_render_overlay_markdown(overlay), encoding="utf-8")
        files["report_json"] = str(json_path)
        files["report_markdown"] = str(md_path)
        payload["files"] = files
    print(json.dumps(payload, indent=2))
    return 0


def _render_overlay_markdown(overlay: "CalibrationOverlay") -> str:
    lines = [
        f"# Measurement calibration — base PDK `{overlay.base_pdk_name}` "
        f"v{overlay.base_pdk_version}",
        "",
        f"- **Status:** **{overlay.calibration_status}** "
        f"(synthetic inputs: {overlay.is_synthetic})",
        f"- **Fabrication readiness:** {overlay.fabrication_readiness}",
        f"- **Base PDK sha256:** `{overlay.base_pdk_hash_sha256}`",
        f"- **Fit method:** {overlay.fit_method}",
        f"- **Fitted:** {overlay.fit_timestamp}",
        f"- Records used: {len(overlay.records_used)} · rejected/unmatched: "
        f"{len(overlay.records_rejected)}",
        "",
        "## Correction factors",
        "",
        "| Factor | Scale | Uncertainty (MAD %) | N | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for factor in overlay.factors.values():
        scale = f"{factor.scale:.6g}" if factor.scale is not None else "—"
        unc = f"{factor.uncertainty_pct:.2f}%" if factor.uncertainty_pct is not None else "—"
        lines.append(f"| {factor.name} | {scale} | {unc} | {factor.n_pairs} | {factor.status} |")
    if overlay.jc_sigma_update_pct is not None:
        lines += ["", f"- Updated wafer-level Jc sigma estimate: {overlay.jc_sigma_update_pct:.3f}%"]
    if overlay.warnings:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in overlay.warnings]
    lines += [
        "",
        "## Honesty statement",
        "",
        "A calibration overlay is NOT foundry qualification. Factors fitted from",
        "synthetic fixtures (SYNTHETIC_CALIBRATION_ONLY) demonstrate the pipeline",
        "and say nothing about any real process. Apply with",
        "`textlayout pdk apply-calibration`; the base PDK file is never edited.",
        "",
    ]
    return "\n".join(lines)


def _cmd_pdk_apply_calibration(args: argparse.Namespace) -> int:
    from textlayout.epr.pdk_bridge import resolve_pdk_path
    from textlayout.measurement import apply_overlay_to_pdk, load_overlay
    from textlayout.pdk.provenance import describe_pdk_file

    overlay = load_overlay(args.overlay)
    base_path = resolve_pdk_path(args.base)
    try:
        out_path = apply_overlay_to_pdk(base_path, overlay, args.out)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    calibrated = describe_pdk_file(out_path)
    print(
        json.dumps(
            {
                "calibrated_pdk": str(out_path),
                "calibrated_pdk_provenance": calibrated.model_dump(mode="json"),
                "base_pdk_hash_sha256": overlay.base_pdk_hash_sha256,
                "calibration_status": overlay.calibration_status,
                "is_synthetic": overlay.is_synthetic,
                "note": "Use the calibrated file downstream, e.g. "
                f"`textlayout epr <spec> --pdk {out_path}`.",
            },
            indent=2,
        )
    )
    return 0


def _cmd_evidence_check(args: argparse.Namespace) -> int:
    """Validate an evidence ledger: schema + every recorded state transition.

    Exit 0 when the chain is legal, 3 when a claim was promoted illegally (for
    example a hand-edited ledger that raised SKIPPED_SOLVER_ABSENT straight to
    PHYSICS_VERIFIED). Intended for CI over stored evidence.
    """
    from textlayout.evidence import EvidenceError, EvidenceLedger

    payload = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    try:
        ledger = EvidenceLedger.from_dict(payload)
    except (EvidenceError, ValueError) as exc:
        print(json.dumps({"ok": False, "ledger": str(args.ledger), "error": str(exc)}, indent=2))
        return 3
    current = ledger.current
    print(
        json.dumps(
            {
                "ok": True,
                "ledger": str(args.ledger),
                "quantity": ledger.quantity,
                "n_records": len(ledger.history),
                "current_status": current.status.value if current else None,
                "current_confidence": (
                    current.confidence_class.name if current else "NONE"
                ),
                "transitions_validated": max(len(ledger.history) - 1, 0),
            },
            indent=2,
        )
    )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from textlayout.doctor import render_text, run_doctor

    report = run_doctor(
        output_dir=args.out,
        strict=args.strict,
        strict_em=args.strict_em,
        strict_fullchip=args.strict_fullchip,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report))
    return 0 if report.ok else 1


def _cmd_jobs_start(args: argparse.Namespace) -> int:
    from textlayout.jobs import record_summary, start_job

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(json.dumps({"error": "missing command; use: textlayout jobs start -- <cmd>"}))
        return 2
    env_overrides: dict[str, str] = {}
    for item in args.env or []:
        if "=" not in item:
            print(json.dumps({"error": f"invalid --env value {item!r}; expected KEY=VALUE"}))
            return 2
        key, value = item.split("=", 1)
        env_overrides[key] = value
    record = start_job(
        command,
        cwd=args.cwd,
        job_root=args.job_root,
        env_overrides=env_overrides,
        inventory_root=args.inventory_root,
    )
    print(json.dumps(record_summary(record), indent=2))
    return 0


def _cmd_jobs_status(args: argparse.Namespace) -> int:
    from textlayout.jobs import record_summary, status_job

    record = status_job(args.job_id, job_root=args.job_root)
    print(json.dumps(record_summary(record), indent=2))
    return 0


def _cmd_jobs_collect(args: argparse.Namespace) -> int:
    from textlayout.jobs import collect_job, record_summary

    record = collect_job(args.job_id, job_root=args.job_root)
    print(json.dumps(record_summary(record), indent=2))
    return 0


def _cmd_jobs_cancel(args: argparse.Namespace) -> int:
    from textlayout.jobs import cancel_job, record_summary

    record = cancel_job(args.job_id, job_root=args.job_root)
    print(json.dumps(record_summary(record), indent=2))
    return 0


def _cmd_jobs_resume(args: argparse.Namespace) -> int:
    from textlayout.jobs import record_summary, resume_job

    record = resume_job(args.job_id, job_root=args.job_root)
    print(json.dumps(record_summary(record), indent=2))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "textlayout.backend.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=False,
    )
    return 0


def _cmd_simulate_palace_resonator(args: argparse.Namespace) -> int:
    from pathlib import Path

    from textlayout.jobs import cancel_job, record_summary, start_job, status_job
    from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
    from textlayout.solvers.palace.benchmark_v017 import (
        AMRSettings,
        palace_resonator_status,
        run_quarter_wave_benchmark_v017,
    )
    from textlayout.solvers.palace.config import DomainExtents
    from textlayout.solvers.palace.models import PalaceBoundedAMRPolicy
    from textlayout.solvers.palace.stages import (
        palace_job_profile_from_payload,
        refresh_stage_job_profiles,
        read_palace_job_profile,
        write_palace_job_profile,
    )

    out_dir = Path(args.out).resolve()
    job_root = Path(args.job_root).resolve() if args.job_root else out_dir / "jobs"

    if args.job_status:
        profile = read_palace_job_profile(out_dir)
        if profile is None:
            print(json.dumps({"error": f"no Palace job profile found in {out_dir}"}))
            return 2
        record = status_job(profile.job_id, job_root=job_root)
        updated = palace_job_profile_from_payload(
            record.model_dump(mode="json"),
            upstream_stage_evidence_ids=profile.upstream_stage_evidence_ids,
        )
        write_palace_job_profile(out_dir, updated)
        refreshed = refresh_stage_job_profiles(out_dir, updated)
        print(
            json.dumps(
                {
                    "schema": "textlayout.palace-job-status.v1",
                    "job": record_summary(record),
                    "profile": updated.model_dump(mode="json", by_alias=True),
                    "refreshed_stage_records": [item.stage for item in refreshed],
                },
                indent=2,
            )
        )
        return 0

    if args.cancel:
        profile = read_palace_job_profile(out_dir)
        if profile is None:
            print(json.dumps({"error": f"no Palace job profile found in {out_dir}"}))
            return 2
        record = cancel_job(profile.job_id, job_root=job_root)
        updated = palace_job_profile_from_payload(
            record.model_dump(mode="json"),
            upstream_stage_evidence_ids=profile.upstream_stage_evidence_ids,
        )
        write_palace_job_profile(out_dir, updated)
        refreshed = refresh_stage_job_profiles(out_dir, updated)
        print(
            json.dumps(
                {
                    "schema": "textlayout.palace-job-cancel.v1",
                    "job": record_summary(record),
                    "profile": updated.model_dump(mode="json", by_alias=True),
                    "refreshed_stage_records": [item.stage for item in refreshed],
                },
                indent=2,
            )
        )
        return 0

    if args.background:
        command = [
            sys.executable,
            "-m",
            "textlayout.cli",
            "simulate",
            "palace-resonator",
            "--out",
            str(out_dir),
            "--resume",
            "--processes",
            str(args.processes),
            "--timeout",
            str(args.timeout),
            "--mesh-scale",
            str(args.mesh_scale),
            "--amr-iterations",
            str(args.amr_iterations),
            "--sweep-amr-iterations",
            str(args.sweep_amr_iterations),
            "--mode-count",
            str(args.mode_count),
        ]
        if args.stage:
            command.extend(["--stage", args.stage])
        if args.from_stage:
            command.extend(["--from-stage", args.from_stage])
        if args.solved_states is not None:
            command.extend(
                [
                    "--solved-states",
                    str(args.solved_states),
                    "--max-rss-gib",
                    str(args.max_rss_gib),
                    "--max-runtime-seconds",
                    str(args.max_runtime_seconds),
                ]
            )
            if args.save_final_mesh:
                command.append("--save-final-mesh")
        if args.bounded_validation_profile:
            command.append("--bounded-validation-profile")
        record = start_job(
            command,
            cwd=Path.cwd(),
            job_root=job_root,
            inventory_root=out_dir,
            env_overrides={"TEXTLAYOUT_PALACE_OUTPUT_DIR": str(out_dir)},
        )
        profile = palace_job_profile_from_payload(record.model_dump(mode="json"))
        write_palace_job_profile(out_dir, profile)
        print(
            json.dumps(
                {
                    "schema": "textlayout.palace-background-job.v1",
                    "job": record_summary(record),
                    "profile": profile.model_dump(mode="json", by_alias=True),
                },
                indent=2,
            )
        )
        return 0

    if args.status:
        print(json.dumps(palace_resonator_status(out_dir), indent=2))
        return 0

    # --sweep-amr-iterations 0 skips the domain/physical sweeps entirely (a
    # reduced preflight that exercises only the base AMR study). A positive
    # value runs the sweeps at that AMR budget; it is not merged with the main
    # study's budget.
    validation_profile = args.bounded_validation_profile
    if validation_profile:
        args.processes = 1
        args.mode_count = 2
        args.mesh_scale = 4.0
        args.solved_states = 2
        args.amr_iterations = 1
        args.sweep_amr_iterations = 0
        args.save_final_mesh = False
    skip_sweeps = args.sweep_amr_iterations == 0
    sweep_kwargs: dict[str, object] = {}
    if skip_sweeps:
        sweep_kwargs = {
            "numerical_sweep_values": {},
            "physical_sweep_values": {},
        }
    else:
        sweep_kwargs = {"sweep_amr": AMRSettings(max_iterations=args.sweep_amr_iterations)}
    bounded_policy = None
    if args.solved_states is not None:
        bounded_policy = PalaceBoundedAMRPolicy(
            solved_states=args.solved_states,
            retain_final_adapted_mesh=args.save_final_mesh,
            perform_adaptation_after_final_solve=args.save_final_mesh,
            save_final_mesh=args.save_final_mesh,
            max_runtime_seconds=args.max_runtime_seconds,
            max_rss_bytes=int(args.max_rss_gib * 1024**3),
            max_elements=200_000 if validation_profile else None,
            max_dofs=2_000_000 if validation_profile else None,
        )
    result = run_quarter_wave_benchmark_v017(
        out_dir,
        layout_path=DEFAULT_LAYOUT,
        processes=args.processes,
        timeout_seconds=args.timeout,
        mesh_scale=args.mesh_scale,
        mode_count=args.mode_count,
        amr=AMRSettings(
            max_iterations=args.amr_iterations,
            bounded_policy=bounded_policy,
        ),
        resume=args.resume,
        stop_after_stage=args.stage,
        from_stage=args.from_stage,
        extents=(
            DomainExtents(
                substrate_thickness_um=150.0,
                vacuum_height_um=150.0,
                lid_height_um=200.0,
                lateral_margin_um=50.0,
            )
            if validation_profile
            else None
        ),
        **sweep_kwargs,  # type: ignore[arg-type]
    )
    print(result.model_dump_json(indent=2))
    return (
        1
        if result.status
        in {
            "SKIPPED_SOLVER_ABSENT",
            "SIMULATION_INVALID",
            "RESOURCE_BUDGET_REJECTED",
            "RESOURCE_LIMIT_TERMINATED",
        }
        else 0
    )


def _cmd_simulate_palace_diagnostic(args: argparse.Namespace) -> int:
    from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
    from textlayout.solvers.palace.diagnostic import run_diagnostic_multimode_catalog

    result = run_diagnostic_multimode_catalog(
        args.out,
        layout_path=DEFAULT_LAYOUT,
        mesh_path=args.mesh,
        fem_model_path=args.fem_model,
        mode_count=args.mode_count,
        processes=1,
        timeout_seconds=args.timeout,
        max_rss_bytes=int(args.max_rss_gib * 1024**3),
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.status in {"OUTPUT_PARSED", "SKIPPED_SOLVER_ABSENT"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="textlayout", description="Text-to-Layout CLI")
    parser.add_argument("--version", action="version", version=f"textlayout {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser(
        "prompt",
        help="Natural-language request -> intent, layout, verification, simulation, report.",
    )
    p_prompt.add_argument(
        "prompt", help="e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'"
    )
    p_prompt.add_argument("--out", default="out/textlayout_prompt", help="Output directory.")
    p_prompt.add_argument("--tolerance", type=float, default=5.0, help="Tolerance in percent.")
    p_prompt.add_argument(
        "--no-solver",
        action="store_true",
        help="Prepare solver inputs but do not attempt to execute a solver.",
    )
    p_prompt.add_argument(
        "--executable",
        default=None,
        help="Explicit component solver path (FasterCap, Octave/openEMS, FastHenry, or JoSIM).",
    )
    p_prompt.add_argument(
        "--strict-simulation",
        action="store_true",
        help="Exit non-zero when a requested circuit simulator (JoSIM/PSCAN2/WRspice) "
        "is not installed. Default: prepare inputs and report the absence honestly.",
    )
    p_prompt.add_argument(
        "--include-epr",
        action="store_true",
        help="Append an EPR_ANALYTICAL_ONLY loss-participation / coherence estimate to "
        "the design report (epr_report.json/.md alongside the usual artifacts). "
        "Capacitance/inductance accuracy does not imply coherence accuracy.",
    )
    p_prompt.set_defaults(func=_cmd_prompt)

    p_gen = sub.add_parser("generate", help="Generate verified artifacts from a DSL file.")
    p_gen.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_gen.add_argument("--out", default="workspace/textlayout", help="Output directory.")
    p_gen.set_defaults(func=_cmd_generate)

    p_ver = sub.add_parser("verify", help="Verify a DSL file (no export).")
    p_ver.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_ver.add_argument(
        "--include-epr",
        action="store_true",
        help="Append an EPR_ANALYTICAL_ONLY loss-participation / coherence estimate "
        "to the verification report.",
    )
    p_ver.add_argument(
        "--frequency-ghz",
        type=float,
        default=None,
        help="Frequency for the EPR coherence estimate (default: spec target or 6 GHz).",
    )
    p_ver.set_defaults(func=_cmd_verify)

    p_epr = sub.add_parser(
        "epr",
        help="Loss-participation (EPR) and coherence estimate for a DSL file. "
        "EPR_ANALYTICAL_ONLY by default; never a field solution.",
    )
    p_epr.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_epr.add_argument(
        "--frequency-ghz",
        type=float,
        default=None,
        help="Analysis frequency (default: spec target frequency or 6 GHz).",
    )
    p_epr.add_argument(
        "--out",
        default="out/evidence",
        help="Directory for epr_report.json / epr_report.md (default: out/evidence).",
    )
    p_epr.add_argument(
        "--pdk",
        default=None,
        help="PDK name (e.g. generic_2metal) or YAML path backing the material "
        "assumptions; recorded with file hash in the report. Default: "
        "generic_2metal (illustrative, NOT fabrication-ready).",
    )
    p_epr.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the EPR backend is unavailable (skipped).",
    )
    p_epr.set_defaults(func=_cmd_epr)

    p_evidence = sub.add_parser(
        "evidence",
        help="Inspect and validate evidence ledgers (the source of truth for "
        "every physics claim).",
    )
    evidence_sub = p_evidence.add_subparsers(dest="evidence_command", required=True)

    p_evidence_check = evidence_sub.add_parser(
        "check",
        help="Validate an evidence ledger: re-check the schema and every recorded "
        "state transition. Exits 3 on an illegal confidence promotion.",
    )
    p_evidence_check.add_argument("ledger", help="Path to an evidence-ledger JSON file.")
    p_evidence_check.set_defaults(func=_cmd_evidence_check)

    p_doc = sub.add_parser("doctor", help="Check the environment (imports, solvers, write perms).")
    p_doc.add_argument("--out", default="out", help="Output directory to probe for writability.")
    p_doc.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_doc.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing external solvers as failures. Default: report them as optional.",
    )
    p_doc.add_argument(
        "--strict-em",
        action="store_true",
        help="Require openEMS, CSXCAD, Octave interfaces, and scikit-rf.",
    )
    p_doc.add_argument(
        "--strict-fullchip",
        action="store_true",
        help="Require Palace, Gmsh, and meshio for the future full-chip FEM path.",
    )
    p_doc.set_defaults(func=_cmd_doctor)

    p_jobs = sub.add_parser(
        "jobs",
        help="Start, inspect, collect, cancel, and resume persistent local solver jobs.",
    )
    jobs_sub = p_jobs.add_subparsers(dest="jobs_command", required=True)

    def _add_job_root(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--job-root",
            default="out/jobs",
            help="Directory containing persistent job records.",
        )

    p_jobs_start = jobs_sub.add_parser("start", help="Start a command under job control.")
    _add_job_root(p_jobs_start)
    p_jobs_start.add_argument("--cwd", default=".", help="Working directory for the command.")
    p_jobs_start.add_argument(
        "--inventory-root",
        default=None,
        help="Directory to hash before and after the job. Default: --cwd.",
    )
    p_jobs_start.add_argument(
        "--env",
        action="append",
        default=[],
        help="Environment override as KEY=VALUE. May be repeated.",
    )
    p_jobs_start.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute. Use -- before the command if it starts with an option.",
    )
    p_jobs_start.set_defaults(func=_cmd_jobs_start)

    for name, help_text, func in (
        ("status", "Inspect a job and write a heartbeat sample.", _cmd_jobs_status),
        ("collect", "Collect return code and solver-owned output inventory.", _cmd_jobs_collect),
        ("cancel", "Request cancellation and terminate the process group.", _cmd_jobs_cancel),
        ("resume", "Resume bookkeeping/post-processing without relaunching the solver.", _cmd_jobs_resume),
    ):
        p_job = jobs_sub.add_parser(name, help=help_text)
        _add_job_root(p_job)
        p_job.add_argument("job_id")
        p_job.set_defaults(func=func)

    p_srv = sub.add_parser("serve", help="Run the FastAPI plugin server.")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.set_defaults(func=_cmd_serve)

    p_simulate = sub.add_parser("simulate", help="Run supported external solver benchmarks.")
    simulate_sub = p_simulate.add_subparsers(dest="simulate_command", required=True)
    p_palace = simulate_sub.add_parser(
        "palace-resonator", help="Run the real 6 GHz quarter-wave Palace eigenmode benchmark."
    )
    p_palace.add_argument("--out", required=True, help="Benchmark artifact directory.")
    palace_stages = (
        "preflight",
        "base_mesh",
        "base_amr",
        "mode_tracking",
        "numerical_sweeps",
        "physical_sensitivity",
        "evidence_promotion",
        "packet_generation",
    )
    p_palace.add_argument(
        "--status",
        action="store_true",
        help="Inspect persisted Palace stage records and active Palace/MPI processes.",
    )
    p_palace.add_argument(
        "--background",
        action="store_true",
        help="Start the Palace resonator workflow under persistent job control. "
        "The managed command always uses --resume so matching completed stages are reused.",
    )
    p_palace.add_argument(
        "--job-status",
        action="store_true",
        help="Inspect the persistent job record linked to this Palace output directory.",
    )
    p_palace.add_argument(
        "--cancel",
        action="store_true",
        help="Cancel the persistent Palace job linked to this output directory.",
    )
    p_palace.add_argument(
        "--job-root",
        default=None,
        help="Persistent job directory for --background/--job-status/--cancel. "
        "Default: <out>/jobs.",
    )
    p_palace.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed stages whose output hashes validate; do not rerun base AMR.",
    )
    p_palace.add_argument(
        "--stage",
        choices=palace_stages,
        default=None,
        help="Run only through the named resumable stage.",
    )
    p_palace.add_argument(
        "--from-stage",
        choices=palace_stages,
        default=None,
        help="Resume from the named stage, reusing prior stage artifacts when hashes match.",
    )
    p_palace.add_argument("--processes", type=int, default=4, help="Palace MPI process count.")
    p_palace.add_argument(
        "--timeout", type=float, default=7200.0, help="Timeout per Palace solve in seconds."
    )
    p_palace.add_argument(
        "--mesh-scale",
        type=float,
        default=3.0,
        help="Base-mesh density factor for the validated simplex mesh AMR refines "
        "from. The element count is U-shaped in this factor (fine local "
        "refinement dominates at low values, extreme grading at high values), "
        "with a practical minimum near 3.0 (~1e5 tets); values far from 3 "
        "produce much larger meshes.",
    )
    p_palace.add_argument(
        "--amr-iterations",
        type=int,
        default=5,
        help="Palace AMR MaxIts for the main study; at least 4 accepted iterations "
        "are required by the gates.",
    )
    p_palace.add_argument(
        "--sweep-amr-iterations",
        type=int,
        default=2,
        help="Palace AMR MaxIts for the domain/physical sweeps. 0 skips the sweeps "
        "entirely (a reduced preflight running only the base AMR study). A lower "
        "positive value keeps the many sweep solves tractable.",
    )
    p_palace.add_argument(
        "--mode-count",
        type=int,
        default=4,
        help="Number of Palace eigenmodes to solve and retain per iteration.",
    )
    p_palace.add_argument(
        "--solved-states",
        type=int,
        default=None,
        help="Enable bounded AMR with this exact number of solved states.",
    )
    p_palace.add_argument(
        "--max-rss-gib",
        type=float,
        default=8.0,
        help="Hard process-group RSS limit for a bounded Palace run.",
    )
    p_palace.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=1200,
        help="Hard solver runtime limit for a bounded Palace run.",
    )
    p_palace.add_argument(
        "--save-final-mesh",
        action="store_true",
        help="Explicitly request adaptation and serialization after the final solved state.",
    )
    p_palace.add_argument(
        "--bounded-validation-profile",
        action="store_true",
        help=(
            "Run the one-rank, two-mode, two-state coarse operational validation "
            "profile with one refinement, no sweeps, and no final mesh serialization."
        ),
    )
    p_palace.set_defaults(func=_cmd_simulate_palace_resonator)

    p_diagnostic = simulate_sub.add_parser(
        "palace-diagnostic",
        help="Run a bounded one-state Palace multimode classification catalog.",
    )
    p_diagnostic.add_argument("--out", required=True)
    p_diagnostic.add_argument("--mesh", required=True)
    p_diagnostic.add_argument("--fem-model", required=True)
    p_diagnostic.add_argument("--mode-count", type=int, default=8, choices=range(6, 11))
    p_diagnostic.add_argument("--timeout", type=float, default=1200.0)
    p_diagnostic.add_argument("--max-rss-gib", type=float, default=7.0)
    p_diagnostic.set_defaults(func=_cmd_simulate_palace_diagnostic)

    p_yield = sub.add_parser(
        "yield",
        help="JJ critical-current variability / fabrication-yield Monte Carlo. "
        "Drawing one SQUID loop proves geometry, not manufacturability.",
    )
    yield_sub = p_yield.add_subparsers(dest="yield_command", required=True)

    def _add_process_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--jc", type=float, required=True, help="Target Jc (uA/um^2).")
        p.add_argument(
            "--wafer-sigma-pct",
            type=float,
            required=True,
            help="Wafer-to-wafer Jc sigma (%% of mean).",
        )
        p.add_argument(
            "--local-sigma-pct",
            type=float,
            required=True,
            help="Junction-to-junction local Jc sigma (%% of mean).",
        )
        p.add_argument(
            "--cd-sigma-nm",
            type=float,
            default=0.0,
            help="Lithography CD sigma per linear dimension (nm).",
        )
        p.add_argument(
            "--area-bias-um2",
            type=float,
            default=0.0,
            help="Systematic junction-area bias (um^2).",
        )
        p.add_argument(
            "--gradient-pct-per-mm",
            type=float,
            default=0.0,
            help="Optional linear Jc gradient across the chip (%% of mean per mm).",
        )
        p.add_argument("--width-um", type=float, required=True, help="Drawn junction width (um).")
        p.add_argument("--height-um", type=float, required=True, help="Drawn junction height (um).")
        p.add_argument("--shunt-c-pf", type=float, required=True, help="Shunt capacitance (pF).")
        p.add_argument("--target-ghz", type=float, required=True, help="Target frequency (GHz).")
        p.add_argument(
            "--tolerance-mhz",
            type=float,
            required=True,
            help="Acceptance half-window (MHz).",
        )
        p.add_argument("--seed", type=int, default=1234, help="Monte Carlo seed (reproducible).")
        p.add_argument("--out", default=None, help="Directory for the JSON/Markdown yield report.")

    p_yield_jj = yield_sub.add_parser(
        "jj", help="Single junction/mode yield: frequency distribution, hit rate, CI95."
    )
    _add_process_args(p_yield_jj)
    p_yield_jj.add_argument("--n-samples", type=int, default=5000, help="Monte Carlo sample count.")
    p_yield_jj.set_defaults(func=_cmd_yield_jj)

    p_yield_array = yield_sub.add_parser(
        "qubit-array",
        help="Chip-level yield: probability that ALL qubits on a chip are simultaneously in spec.",
    )
    _add_process_args(p_yield_array)
    p_yield_array.add_argument(
        "--n-qubits", type=int, required=True, help="Qubits per chip that must all pass."
    )
    p_yield_array.add_argument(
        "--n-chips", type=int, default=2000, help="Simulated chips (Monte Carlo trials)."
    )
    p_yield_array.add_argument(
        "--qubit-pitch-mm",
        type=float,
        default=1.0,
        help="Synthetic qubit placement pitch for the spatial gradient (mm).",
    )
    p_yield_array.set_defaults(func=_cmd_yield_qubit_array)

    p_chip = sub.add_parser(
        "chip",
        help="Multi-qubit chip-level frequency-collision analysis. A single-device "
        "closed loop cannot answer whether a processor works.",
    )
    chip_sub = p_chip.add_subparsers(dest="chip_command", required=True)

    p_chip_analyze = chip_sub.add_parser(
        "analyze",
        help="Deterministic + Monte Carlo collision analysis of a qubit lattice JSON file.",
    )
    p_chip_analyze.add_argument("lattice", help="Path to a QubitLattice JSON file.")
    p_chip_analyze.add_argument(
        "--n-samples", type=int, default=2000, help="Monte Carlo sample count."
    )
    p_chip_analyze.add_argument("--seed", type=int, default=1234, help="Monte Carlo seed.")
    p_chip_analyze.add_argument(
        "--out",
        default=None,
        help="Directory for chip_yield_report.json/.md and collision_matrix.csv.",
    )
    p_chip_analyze.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the nominal (target-frequency) lattice has any collision.",
    )
    p_chip_analyze.set_defaults(func=_cmd_chip_analyze)

    p_chip_optimize = chip_sub.add_parser(
        "optimize",
        help="Greedily retune target frequencies to reduce/eliminate collisions.",
    )
    p_chip_optimize.add_argument("lattice", help="Path to a QubitLattice JSON file.")
    p_chip_optimize.add_argument(
        "--max-retune-mhz",
        type=float,
        default=300.0,
        help="Max allowed retune from each qubit's original target (MHz).",
    )
    p_chip_optimize.add_argument(
        "--step-mhz", type=float, default=5.0, help="Greedy search step size (MHz)."
    )
    p_chip_optimize.add_argument(
        "--out",
        default=None,
        help="Directory for chip_optimize_report.json/.md.",
    )
    p_chip_optimize.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the optimizer does not reach a collision-free result.",
    )
    p_chip_optimize.set_defaults(func=_cmd_chip_optimize)

    p_pdk = sub.add_parser(
        "pdk",
        help="Foundry PDK abstraction: list registered technologies or inspect a PDK's "
        "full provenance and process parameters.",
    )
    pdk_sub = p_pdk.add_subparsers(dest="pdk_command", required=True)

    p_pdk_list = pdk_sub.add_parser(
        "list", help="List all registered technology names (LayoutSpec.technology values)."
    )
    p_pdk_list.set_defaults(func=_cmd_pdk_list)

    p_pdk_info = pdk_sub.add_parser(
        "info", help="Print full PDK metadata (version, foundry_validated, layers, source)."
    )
    p_pdk_info.add_argument("name", help="PDK name, e.g. 'example_superconducting_pdk'.")
    p_pdk_info.set_defaults(func=_cmd_pdk_info)

    p_pdk_apply = pdk_sub.add_parser(
        "apply-calibration",
        help="Apply a calibration overlay to a base PDK, writing a NEW calibrated "
        "PDK file (the base is never edited). Synthetic overlays yield an "
        "illustrative-status PDK, never internal/foundry calibrated.",
    )
    p_pdk_apply.add_argument(
        "--base", required=True, help="Base PDK name or YAML path the overlay was fitted against."
    )
    p_pdk_apply.add_argument(
        "--overlay", required=True, help="Path to calibrated_pdk_overlay.yaml."
    )
    p_pdk_apply.add_argument(
        "--out", required=True, help="Output path for the calibrated PDK YAML (must differ from base)."
    )
    p_pdk_apply.set_defaults(func=_cmd_pdk_apply_calibration)

    p_measurement = sub.add_parser(
        "measurement",
        help="Simulation-vs-measurement correlation: the path from illustrative to "
        "fab-calibrated numbers.",
    )
    measurement_sub = p_measurement.add_subparsers(dest="measurement_command", required=True)

    p_meas_compare = measurement_sub.add_parser(
        "compare",
        help="Residual table: simulated/predicted vs measured, per device per quantity.",
    )
    p_meas_compare.add_argument(
        "--predicted", required=True, help="Path to a JSON list of SimulatedPrediction."
    )
    p_meas_compare.add_argument(
        "--measured",
        required=True,
        help="Path to MeasurementRecord data: JSON list or CSV (columns = field names).",
    )
    p_meas_compare.add_argument(
        "--out",
        default=None,
        help="Directory for measurement_residuals.csv and "
        "measurement_comparison_report.json/.md.",
    )
    p_meas_compare.set_defaults(func=_cmd_measurement_compare)

    p_meas_calibrate = measurement_sub.add_parser(
        "calibrate",
        help="Fit capacitance/inductance/loss-tangent/Jc correction factors from measurements.",
    )
    p_meas_calibrate.add_argument(
        "--predicted", required=True, help="Path to a JSON list of SimulatedPrediction."
    )
    p_meas_calibrate.add_argument(
        "--measured",
        required=True,
        help="Path to MeasurementRecord data: JSON list or CSV (columns = field names).",
    )
    p_meas_calibrate.add_argument(
        "--production",
        action="store_true",
        help="Mark the resulting calibration as non-synthetic (real cooldown data "
        "only). Refused when any input record is flagged synthetic.",
    )
    p_meas_calibrate.add_argument(
        "--base-pdk",
        default="generic_2metal",
        help="Registered PDK name or YAML path the overlay binds to (recorded "
        "with sha256; default: generic_2metal).",
    )
    p_meas_calibrate.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="Minimum matched pairs per factor; below this the factor reports "
        "INSUFFICIENT_MEASUREMENT_DATA instead of a fit.",
    )
    p_meas_calibrate.add_argument(
        "--out",
        default=None,
        help="Directory for calibrated_pdk_overlay.yaml, "
        "measurement_calibration_report.json/.md (plus legacy calibration.yaml).",
    )
    p_meas_calibrate.set_defaults(func=_cmd_measurement_calibrate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
        return result
    except TextLayoutError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
