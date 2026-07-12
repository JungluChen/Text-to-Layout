"""Typed Palace stage artifact contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file

ArtifactRole = Literal["expected_input", "expected_output", "optional_output", "undeclared"]
ArtifactStatus = Literal[
    "present", "missing", "UNCHANGED", "OVERSIZE", "UNDECLARED_OUTPUT"
]

EXCLUDED_ARTIFACT_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tools",
    ".venv",
    "__pycache__",
    "jobs",
    "stages",
}


class ArtifactFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    size_bytes: int
    mtime_ns: int
    sha256: str | None = None


class PalaceArtifactContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str
    expected_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    optional_outputs: list[str] = Field(default_factory=list)
    excluded_dirs: list[str] = Field(default_factory=lambda: sorted(EXCLUDED_ARTIFACT_DIRS))
    excluded_paths: list[str] = Field(default_factory=list)
    maximum_expected_sizes: dict[str, int] = Field(default_factory=dict)
    retention_policy: Literal[
        "compact_permanent",
        "local_raw_expiring",
        "job_evidence_permanent",
    ] = "compact_permanent"
    owned_roots: list[str] = Field(default_factory=list)
    scan_root_files: bool = False


class PalaceArtifactEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    role: ArtifactRole
    status: ArtifactStatus
    size_bytes: int | None = None
    mtime_ns: int | None = None
    sha256: str | None = None


class PalaceArtifactReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: str = Field(
        default="textlayout.palace-artifact-contract-report.v1", alias="schema"
    )
    stage: str
    entries: list[PalaceArtifactEntry]
    undeclared_outputs: list[str] = Field(default_factory=list)

    @property
    def has_undeclared_outputs(self) -> bool:
        return bool(self.undeclared_outputs)


PALACE_ARTIFACT_CONTRACTS: dict[str, PalaceArtifactContract] = {
    "preflight": PalaceArtifactContract(
        stage="preflight",
        expected_outputs=[
            "toolchain.json",
            "environment.json",
            "resource_decision.json",
            "fem_model.json",
        ],
        maximum_expected_sizes={"*.json": 5_000_000},
        scan_root_files=True,
    ),
    "base_mesh": PalaceArtifactContract(
        stage="base_mesh",
        expected_inputs=["fem_model.json"],
        expected_outputs=[
            "base_mesh/mesh_metrics.json",
            "base_mesh/quarter_wave_base.msh",
        ],
        maximum_expected_sizes={
            "base_mesh/mesh_metrics.json": 5_000_000,
            "base_mesh/quarter_wave_base.msh": 2_000_000_000,
        },
        retention_policy="local_raw_expiring",
        owned_roots=["base_mesh"],
    ),
    "base_amr": PalaceArtifactContract(
        stage="base_amr",
        expected_inputs=[
            "base_mesh/palace_amr.json",
            "base_mesh/quarter_wave_base.msh",
        ],
        expected_outputs=[
            "base_mesh/palace.stdout.txt",
            "base_mesh/palace.stderr.txt",
            "base_mesh/postpro/eig.csv",
            "base_mesh/postpro/domain-E.csv",
            "base_mesh/postpro/error-indicators.csv",
        ],
        optional_outputs=[
            "base_mesh/mesh_metrics.json",
            "base_mesh/quarter_wave_base.msh",
            "base_mesh/palace_amr.json",
            "base_mesh/postpro/*_resolved.json",
            "base_mesh/postpro/**/*.mesh",
            "raw/final_adapted.mesh",
        ],
        maximum_expected_sizes={
            "base_mesh/postpro/**/*.mesh": 8_000_000_000,
            "raw/final_adapted.mesh": 8_000_000_000,
            "base_mesh/postpro/**/*.pvtu": 1_000_000_000,
            "base_mesh/postpro/**/*.vtu": 8_000_000_000,
        },
        retention_policy="local_raw_expiring",
        owned_roots=["base_mesh", "raw"],
    ),
    "mode_tracking": PalaceArtifactContract(
        stage="mode_tracking",
        expected_inputs=[
            "base_mesh/postpro/eig.csv",
            "base_mesh/postpro/domain-E.csv",
        ],
        expected_outputs=["mode_tracking.json", "convergence.json"],
        maximum_expected_sizes={"*.json": 50_000_000},
        scan_root_files=True,
        excluded_paths=[
            "toolchain.json",
            "environment.json",
            "resource_decision.json",
            "fem_model.json",
            "palace_job_profile.json",
        ],
    ),
    "numerical_sweeps": PalaceArtifactContract(
        stage="numerical_sweeps",
        expected_inputs=["mode_tracking.json"],
        optional_outputs=[
            "numerical_domain_sweeps/**/*.json",
            "numerical_domain_sweeps/**/*.csv",
            "numerical_domain_sweeps/**/*.txt",
        ],
        maximum_expected_sizes={"numerical_domain_sweeps/**/*": 8_000_000_000},
        retention_policy="local_raw_expiring",
        owned_roots=["numerical_domain_sweeps"],
    ),
    "physical_sensitivity": PalaceArtifactContract(
        stage="physical_sensitivity",
        expected_inputs=["mode_tracking.json"],
        optional_outputs=[
            "physical_sensitivity/**/*.json",
            "physical_sensitivity/**/*.csv",
            "physical_sensitivity/**/*.txt",
        ],
        maximum_expected_sizes={"physical_sensitivity/**/*": 8_000_000_000},
        retention_policy="local_raw_expiring",
        owned_roots=["physical_sensitivity"],
    ),
    "evidence_promotion": PalaceArtifactContract(
        stage="evidence_promotion",
        expected_inputs=["convergence.json", "run_manifest.json"],
        expected_outputs=["canonical_evidence.json"],
        maximum_expected_sizes={"canonical_evidence.json": 50_000_000},
        scan_root_files=True,
        excluded_paths=[
            "toolchain.json",
            "environment.json",
            "resource_decision.json",
            "fem_model.json",
            "palace_job_profile.json",
            "mode_tracking.json",
            "report.md",
        ],
    ),
    "packet_generation": PalaceArtifactContract(
        stage="packet_generation",
        expected_inputs=["canonical_evidence.json"],
        expected_outputs=[
            "base_amr_validation.json",
            "convergence.json",
            "engineering_report.md",
            "resource_summary.json",
            "run_manifest.json",
        ],
        maximum_expected_sizes={"*": 100_000_000},
        scan_root_files=True,
        excluded_paths=[
            "toolchain.json",
            "environment.json",
            "resource_decision.json",
            "fem_model.json",
            "palace_job_profile.json",
            "mode_tracking.json",
            "canonical_evidence.json",
        ],
    ),
}


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_excluded(path: Path, root: Path, contract: PalaceArtifactContract) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    relative_text = relative.as_posix()
    return any(part in set(contract.excluded_dirs) for part in relative.parts) or _matches_any(
        relative_text, contract.excluded_paths
    )


def _maximum_size(path: str, contract: PalaceArtifactContract) -> int | None:
    matches = [
        limit
        for pattern, limit in contract.maximum_expected_sizes.items()
        if Path(path).match(pattern)
    ]
    return min(matches) if matches else None


def _matches_any(path: str, patterns: list[str]) -> bool:
    probe = Path(path)
    return any(probe.match(pattern) for pattern in patterns)


def _fingerprint(
    path: Path,
    root: Path,
    previous: dict[str, ArtifactFingerprint],
) -> ArtifactFingerprint:
    relative = _relative(path, root)
    stat = path.stat()
    prior = previous.get(relative)
    if (
        prior is not None
        and prior.size_bytes == stat.st_size
        and prior.mtime_ns == stat.st_mtime_ns
        and prior.sha256 is not None
    ):
        return prior
    return ArtifactFingerprint(
        path=relative,
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=sha256_file(path),
    )


def _collect_declared_matches(root: Path, patterns: list[str]) -> set[str]:
    matches: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                matches.add(_relative(path, root))
    return matches


def scan_palace_artifacts(
    root: str | Path,
    stage: str,
    *,
    previous_manifest: dict[str, ArtifactFingerprint] | None = None,
) -> PalaceArtifactReport:
    """Scan one stage against its declared Palace artifact contract."""
    root_path = Path(root).resolve()
    contract = PALACE_ARTIFACT_CONTRACTS[stage]
    previous = previous_manifest or {}
    entries: list[PalaceArtifactEntry] = []
    declared_patterns = [
        *contract.expected_inputs,
        *contract.expected_outputs,
        *contract.optional_outputs,
    ]
    declared_matches = _collect_declared_matches(root_path, declared_patterns)

    for role, patterns in (
        ("expected_input", contract.expected_inputs),
        ("expected_output", contract.expected_outputs),
        ("optional_output", contract.optional_outputs),
    ):
        for pattern in patterns:
            matches = sorted(_collect_declared_matches(root_path, [pattern]))
            if not matches and role != "optional_output":
                entries.append(
                    PalaceArtifactEntry(path=pattern, role=role, status="missing")
                )
                continue
            for relative in matches:
                fingerprint = _fingerprint(root_path / relative, root_path, previous)
                status: ArtifactStatus = (
                    "UNCHANGED"
                    if previous.get(relative) == fingerprint
                    else "present"
                )
                maximum = _maximum_size(relative, contract)
                if maximum is not None and fingerprint.size_bytes > maximum:
                    status = "OVERSIZE"
                entries.append(
                    PalaceArtifactEntry(
                        path=relative,
                        role=role,
                        status=status,
                        size_bytes=fingerprint.size_bytes,
                        mtime_ns=fingerprint.mtime_ns,
                        sha256=fingerprint.sha256,
                    )
                )

    candidates: set[Path] = set()
    for owned_root in contract.owned_roots:
        stage_root = root_path / owned_root
        if stage_root.is_dir():
            candidates.update(path for path in stage_root.rglob("*") if path.is_file())
    if contract.scan_root_files:
        candidates.update(path for path in root_path.iterdir() if path.is_file())

    undeclared: list[str] = []
    for path in sorted(candidates):
        if not path.is_file() or _is_excluded(path, root_path, contract):
            continue
        relative = _relative(path, root_path)
        if relative in declared_matches or _matches_any(relative, declared_patterns):
            continue
        fingerprint = _fingerprint(path, root_path, previous)
        undeclared.append(relative)
        entries.append(
            PalaceArtifactEntry(
                path=relative,
                role="undeclared",
                status="UNDECLARED_OUTPUT",
                size_bytes=fingerprint.size_bytes,
                mtime_ns=fingerprint.mtime_ns,
                sha256=fingerprint.sha256,
            )
        )

    return PalaceArtifactReport(
        stage=stage,
        entries=sorted(entries, key=lambda entry: (entry.path, entry.role)),
        undeclared_outputs=sorted(undeclared),
    )
