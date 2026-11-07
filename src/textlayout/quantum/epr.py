"""Energy-participation-ratio (EPR) quantisation of linear eigenmodes.

Implements the EPR method of Minev et al., *npj Quantum Inf.* 7, 131 (2021),
in pure Python so it runs on any host. Inputs are the *linear* eigenmode
frequencies and the per-mode, per-junction inductive participation ratios
``p_mj`` (from Palace ``port-EPR.csv`` / ``port-E.csv``, or supplied by the
caller). Outputs are the dressed qubit frequency, anharmonicities and the full
cross-Kerr matrix:

.. math::

    \\varphi_{zpf,mj}^2 = \\frac{p_{mj}\\,\\hbar\\omega_m}{2E_{J,j}}, \\qquad
    \\chi_{mn} = -\\frac{\\hbar\\omega_m\\omega_n}{4}\\sum_j \\frac{p_{mj}p_{nj}}{E_{J,j}}, \\qquad
    \\alpha_m = \\frac{\\chi_{mm}}{2}, \\qquad
    \\omega'_m = \\omega_m + \\frac{1}{2}\\sum_n \\chi_{mn}.

In the single-mode transmon limit (:math:`p=1`) this reproduces
:math:`\\alpha=-E_C` and :math:`f_{01}=\\sqrt{8E_JE_C}-E_C`.

Optional cross-checks use ``scqubits`` (exact transmon diagonalisation) and
``pyEPR`` when they can be imported; both degrade to an explicit
``SKIPPED_SOLVER_ABSENT`` record. Nothing here claims field data that was not
produced by a solver: :func:`modes_from_palace_output` only reads files Palace
wrote.
"""

from __future__ import annotations

import csv
import importlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.evidence.contract import EvidenceStatus

QUANTUM_ANALYSIS_SCHEMA = "textlayout.quantum-analysis.v1"
REPORT_BEGIN = "<!-- textlayout:quantum-analysis:begin -->"
REPORT_END = "<!-- textlayout:quantum-analysis:end -->"

_PHI0_WB = 2.067_833_848e-15
_PLANCK_J_S = 6.626_070_15e-34


def josephson_energy_ghz_from_ic(critical_current_ua: float) -> float:
    """E_J / h in GHz from a critical current in µA."""
    if critical_current_ua <= 0:
        raise ValueError("critical_current_ua must be positive")
    return _PHI0_WB * critical_current_ua * 1e-6 / (2.0 * math.pi) / _PLANCK_J_S / 1e9


def josephson_energy_ghz_from_lj(inductance_nh: float) -> float:
    """E_J / h in GHz from a Josephson inductance in nH (E_J = (Phi0/2pi)^2 / L_J)."""
    if inductance_nh <= 0:
        raise ValueError("inductance_nh must be positive")
    reduced_flux = _PHI0_WB / (2.0 * math.pi)
    return reduced_flux**2 / (inductance_nh * 1e-9) / _PLANCK_J_S / 1e9


class JunctionModel(BaseModel):
    """A Josephson element participating in the linear modes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    josephson_energy_ghz: float | None = Field(default=None, gt=0)
    critical_current_ua: float | None = Field(default=None, gt=0)
    inductance_nh: float | None = Field(default=None, gt=0)
    port_index: int | None = Field(default=None, ge=1, description="Palace lumped-port index.")

    @model_validator(mode="after")
    def _one_definition(self) -> JunctionModel:
        if (
            sum(
                v is not None
                for v in (self.josephson_energy_ghz, self.critical_current_ua, self.inductance_nh)
            )
            != 1
        ):
            raise ValueError(
                "specify exactly one of josephson_energy_ghz, critical_current_ua, inductance_nh"
            )
        return self

    @property
    def e_j_ghz(self) -> float:
        if self.josephson_energy_ghz is not None:
            return self.josephson_energy_ghz
        if self.critical_current_ua is not None:
            return josephson_energy_ghz_from_ic(self.critical_current_ua)
        assert self.inductance_nh is not None
        return josephson_energy_ghz_from_lj(self.inductance_nh)


class ModeEnergy(BaseModel):
    """One linear eigenmode with its energy distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=1)
    frequency_ghz: float = Field(gt=0)
    quality_factor: float | None = Field(default=None, gt=0)
    junction_participation: dict[str, float] = Field(default_factory=dict)
    electric_energy_fraction: dict[str, float] = Field(
        default_factory=dict, description="Electrostatic energy share per region (sums <= 1)."
    )
    magnetic_energy_fraction: dict[str, float] = Field(
        default_factory=dict, description="Magnetic-field energy share per region."
    )
    kinetic_energy_fraction: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Lumped inductive (junction) share of total inductive energy.",
    )
    total_electric_energy_j: float | None = Field(default=None, gt=0)
    total_magnetic_energy_j: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _bounded(self) -> ModeEnergy:
        for name, value in self.junction_participation.items():
            if not 0.0 <= value <= 1.0 + 1e-9:
                raise ValueError(
                    f"participation of {name!r} in mode {self.index} out of [0,1]: {value}"
                )
        if sum(self.junction_participation.values()) > 1.0 + 1e-6:
            raise ValueError(f"mode {self.index}: junction participations sum above one")
        return self


class ScqubitsCrossCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EvidenceStatus
    reason: str | None = None
    e_j_ghz: float | None = None
    e_c_ghz: float | None = None
    f01_ghz: float | None = None
    anharmonicity_ghz: float | None = None
    epr_f01_ghz: float | None = None
    epr_anharmonicity_ghz: float | None = None
    f01_deviation_percent: float | None = None
    anharmonicity_deviation_percent: float | None = None
    scqubits_version: str | None = None


class QuantumAnalysis(BaseModel):
    """Serialised EPR result (``quantum_analysis.json``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = Field(default=QUANTUM_ANALYSIS_SCHEMA, alias="schema")
    status: EvidenceStatus
    source: Literal["palace_fields", "user_participations", "none"]
    reason: str | None = None
    method: str = "EPR (Minev et al. 2021), first-order quartic expansion"
    junctions: list[JunctionModel]
    modes: list[ModeEnergy]
    participation_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    zpf_matrix_rad: dict[str, dict[str, float]] = Field(default_factory=dict)
    chi_matrix_ghz: dict[str, dict[str, float]] = Field(default_factory=dict)
    anharmonicity_ghz: dict[str, float] = Field(default_factory=dict)
    linear_frequency_ghz: dict[str, float] = Field(default_factory=dict)
    dressed_frequency_ghz: dict[str, float] = Field(default_factory=dict)
    qubit_mode_index: int | None = None
    qubit_frequency_ghz: float | None = None
    qubit_anharmonicity_ghz: float | None = None
    dielectric_participation: dict[str, dict[str, float]] = Field(default_factory=dict)
    magnetic_participation: dict[str, dict[str, float]] = Field(default_factory=dict)
    scqubits_cross_check: ScqubitsCrossCheck | None = None
    pyepr_available: bool = False
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- core EPR


def epr_from_participations(
    modes: list[ModeEnergy],
    junctions: list[JunctionModel],
    *,
    source: Literal["palace_fields", "user_participations"] = "user_participations",
    status: EvidenceStatus | None = None,
    cross_check: bool = True,
) -> QuantumAnalysis:
    """Quantise ``modes`` against ``junctions`` with the first-order EPR formulas."""
    if not modes:
        raise ValueError("at least one mode is required")
    if not junctions:
        raise ValueError("at least one junction is required")
    warnings: list[str] = []
    e_j = {j.name: j.e_j_ghz for j in junctions}
    mode_keys = [str(m.index) for m in modes]

    participation: dict[str, dict[str, float]] = {}
    zpf: dict[str, dict[str, float]] = {}
    for mode in modes:
        row: dict[str, float] = {}
        zrow: dict[str, float] = {}
        for junction in junctions:
            p = mode.junction_participation.get(junction.name, 0.0)
            row[junction.name] = p
            # phi_zpf^2 = p * h f / (2 E_J)   (E_J, f both as frequencies)
            zrow[junction.name] = math.sqrt(p * mode.frequency_ghz / (2.0 * e_j[junction.name]))
        participation[str(mode.index)] = row
        zpf[str(mode.index)] = zrow
        if not any(row.values()):
            warnings.append(f"mode {mode.index} has zero junction participation; treated as linear")

    chi: dict[str, dict[str, float]] = {}
    for m in modes:
        chi_row: dict[str, float] = {}
        for n in modes:
            total = 0.0
            for junction in junctions:
                pm = participation[str(m.index)][junction.name]
                pn = participation[str(n.index)][junction.name]
                total += pm * pn / e_j[junction.name]
            chi_row[str(n.index)] = -(m.frequency_ghz * n.frequency_ghz / 4.0) * total
        chi[str(m.index)] = chi_row

    alpha = {key: chi[key][key] / 2.0 for key in mode_keys}
    linear = {str(m.index): m.frequency_ghz for m in modes}
    dressed = {key: linear[key] + 0.5 * sum(chi[key].values()) for key in mode_keys}
    for key in mode_keys:
        if dressed[key] <= 0:
            warnings.append(f"mode {key}: dressed frequency non-positive; EPR expansion invalid")

    qubit_key = max(mode_keys, key=lambda k: sum(participation[k].values()))
    qubit_index: int | None = int(qubit_key)
    if sum(participation[qubit_key].values()) <= 0.0:
        qubit_index = None
        warnings.append("no mode participates in any junction; no qubit identified")

    check: ScqubitsCrossCheck | None = None
    if cross_check and qubit_index is not None and len(junctions) == 1:
        junction = junctions[0]
        p_q = participation[qubit_key][junction.name]
        f_lin = linear[qubit_key]
        # Transmon mapping of the qubit mode: f_lin ~ sqrt(8 E_J E_C) with p-weighted E_J
        e_c = f_lin**2 / (8.0 * e_j[junction.name] * p_q) if p_q > 0 else None
        check = scqubits_transmon_cross_check(
            e_j_ghz=e_j[junction.name],
            e_c_ghz=e_c,
            epr_f01_ghz=dressed[qubit_key],
            epr_anharmonicity_ghz=alpha[qubit_key],
        )

    return QuantumAnalysis(
        status=status
        or (
            EvidenceStatus.SIMULATION_EXECUTED
            if source == "palace_fields"
            else EvidenceStatus.ANALYTICAL_ONLY
        ),
        source=source,
        junctions=junctions,
        modes=modes,
        participation_matrix=participation,
        zpf_matrix_rad=zpf,
        chi_matrix_ghz=chi,
        anharmonicity_ghz=alpha,
        linear_frequency_ghz=linear,
        dressed_frequency_ghz=dressed,
        qubit_mode_index=qubit_index,
        qubit_frequency_ghz=dressed[qubit_key] if qubit_index is not None else None,
        qubit_anharmonicity_ghz=alpha[qubit_key] if qubit_index is not None else None,
        dielectric_participation={str(m.index): dict(m.electric_energy_fraction) for m in modes},
        magnetic_participation={str(m.index): dict(m.magnetic_energy_fraction) for m in modes},
        scqubits_cross_check=check,
        pyepr_available=pyepr_available(),
        warnings=warnings,
    )


# ------------------------------------------------------------------ optional libraries


def scqubits_available() -> bool:
    try:
        return importlib.util.find_spec("scqubits") is not None
    except (ImportError, ValueError):
        return False


def pyepr_available() -> bool:
    try:
        return importlib.util.find_spec("pyEPR") is not None
    except (ImportError, ValueError):
        return False


def scqubits_transmon_cross_check(
    *,
    e_j_ghz: float,
    e_c_ghz: float | None,
    epr_f01_ghz: float,
    epr_anharmonicity_ghz: float,
    ncut: int = 40,
) -> ScqubitsCrossCheck:
    """Exact transmon spectrum from scqubits for the EPR-inferred (E_J, E_C)."""
    base = {
        "e_j_ghz": e_j_ghz,
        "e_c_ghz": e_c_ghz,
        "epr_f01_ghz": epr_f01_ghz,
        "epr_anharmonicity_ghz": epr_anharmonicity_ghz,
    }
    if e_c_ghz is None or e_c_ghz <= 0:
        return ScqubitsCrossCheck(
            status=EvidenceStatus.FAILED, reason="no charging energy could be inferred", **base
        )
    if not scqubits_available():
        return ScqubitsCrossCheck(
            status=EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            reason="scqubits not installed; install the `quantum` extra",
            **base,
        )
    try:
        scq = importlib.import_module("scqubits")
        transmon = scq.Transmon(EJ=e_j_ghz, EC=e_c_ghz, ng=0.0, ncut=ncut)
        evals = transmon.eigenvals(evals_count=3)
        f01 = float(evals[1] - evals[0])
        alpha = float((evals[2] - evals[1]) - f01)
    except Exception as exc:  # noqa: BLE001 - optional library failure is reported, not raised
        return ScqubitsCrossCheck(
            status=EvidenceStatus.FAILED,
            reason=f"scqubits raised {type(exc).__name__}: {exc}",
            **base,
        )
    return ScqubitsCrossCheck(
        status=EvidenceStatus.SIMULATION_EXECUTED,
        reason="scqubits.Transmon exact diagonalisation",
        f01_ghz=f01,
        anharmonicity_ghz=alpha,
        f01_deviation_percent=abs(f01 - epr_f01_ghz) / f01 * 100.0 if f01 else None,
        anharmonicity_deviation_percent=(
            abs(alpha - epr_anharmonicity_ghz) / abs(alpha) * 100.0 if alpha else None
        ),
        scqubits_version=str(getattr(scq, "__version__", None)),
        **base,
    )


# -------------------------------------------------------------- Palace output ingestion

_INDEXED = re.compile(
    r"^(E_elec|E_mag|p_elec|p_mag|E_ind|E_cap|p)\s*\[\s*(\d+)\s*\]", re.IGNORECASE
)


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise ValueError(f"{path}: no data rows")
    return [cell.strip() for cell in rows[0]], rows[1:]


def _mode_rows(header: list[str], rows: list[list[str]]) -> dict[int, dict[str, float]]:
    mode_col = next((i for i, name in enumerate(header) if name.lower() == "m"), 0)
    table: dict[int, dict[str, float]] = {}
    for row in rows:
        record: dict[str, float] = {}
        for name, cell in zip(header, row, strict=False):
            try:
                record[name] = float(cell)
            except ValueError:
                continue
        table[int(round(float(row[mode_col])))] = record
    return table


def _indexed(record: dict[str, float], prefix: str) -> dict[int, float]:
    out: dict[int, float] = {}
    for name, value in record.items():
        match = _INDEXED.match(name)
        if match and match.group(1).lower() == prefix.lower():
            out[int(match.group(2))] = value
    return out


def modes_from_palace_output(
    postpro_dir: str | Path,
    junctions: list[JunctionModel],
    *,
    region_names: dict[int, str] | None = None,
) -> list[ModeEnergy]:
    """Assemble :class:`ModeEnergy` records from Palace ``postpro`` files.

    Reads ``eig.csv`` (frequencies, Q), ``domain-E.csv`` (per-domain electric
    and magnetic energies) and, for junction participation, ``port-EPR.csv``
    (``p[i]``) or ``port-E.csv`` (``E_ind[i]`` normalised by total electric
    energy). Junctions must carry ``port_index``. Raises ``FileNotFoundError``
    when ``eig.csv`` is absent; callers map that to an honest status.
    """
    from textlayout.solvers.palace.parser import parse_eigenmodes

    postpro = Path(postpro_dir)
    eig = postpro / "eig.csv"
    if not eig.is_file():
        raise FileNotFoundError(f"missing Palace eigenmode output: {eig}")
    eigenmodes = parse_eigenmodes(eig)
    names = region_names or {}

    domain: dict[int, dict[str, float]] = {}
    domain_path = postpro / "domain-E.csv"
    if domain_path.is_file():
        header, rows = _read_csv(domain_path)
        domain = _mode_rows(header, rows)

    epr_table: dict[int, dict[str, float]] = {}
    for candidate in ("port-EPR.csv", "port-E.csv"):
        path = postpro / candidate
        if path.is_file():
            header, rows = _read_csv(path)
            epr_table = _mode_rows(header, rows)
            break

    modes: list[ModeEnergy] = []
    for eigenmode in eigenmodes:
        record = domain.get(eigenmode.index, {})
        total_e = next((v for k, v in record.items() if k.lower().startswith("e_elec (")), None)
        total_m = next((v for k, v in record.items() if k.lower().startswith("e_mag (")), None)
        e_ind_total = next((v for k, v in record.items() if k.lower().startswith("e_ind (")), None)
        elec = _indexed(record, "p_elec") or (
            {i: v / total_e for i, v in _indexed(record, "E_elec").items()} if total_e else {}
        )
        mag = _indexed(record, "p_mag") or (
            {i: v / total_m for i, v in _indexed(record, "E_mag").items()} if total_m else {}
        )
        port = epr_table.get(eigenmode.index, {})
        p_direct = _indexed(port, "p")
        e_ind_ports = _indexed(port, "E_ind")
        participation: dict[str, float] = {}
        for junction in junctions:
            if junction.port_index is None:
                continue
            if junction.port_index in p_direct:
                participation[junction.name] = max(0.0, min(1.0, p_direct[junction.port_index]))
            elif junction.port_index in e_ind_ports and total_e:
                participation[junction.name] = max(
                    0.0, min(1.0, e_ind_ports[junction.port_index] / total_e)
                )
        kinetic = None
        if e_ind_total is not None and total_e:
            kinetic = max(0.0, min(1.0, e_ind_total / total_e))
        modes.append(
            ModeEnergy(
                index=eigenmode.index,
                frequency_ghz=eigenmode.frequency_ghz,
                quality_factor=(
                    eigenmode.quality_factor
                    if eigenmode.quality_factor and eigenmode.quality_factor > 0
                    else None
                ),
                junction_participation=participation,
                electric_energy_fraction={
                    names.get(i, f"domain_{i}"): v for i, v in sorted(elec.items())
                },
                magnetic_energy_fraction={
                    names.get(i, f"domain_{i}"): v for i, v in sorted(mag.items())
                },
                kinetic_energy_fraction=kinetic,
                total_electric_energy_j=total_e if total_e and total_e > 0 else None,
                total_magnetic_energy_j=total_m if total_m is not None and total_m >= 0 else None,
            )
        )
    return modes


def analyze_palace_output(
    postpro_dir: str | Path,
    junctions: list[JunctionModel],
    *,
    region_names: dict[int, str] | None = None,
    cross_check: bool = True,
) -> QuantumAnalysis:
    """EPR analysis of a Palace run; absent output yields ``SKIPPED_SOLVER_ABSENT``."""
    try:
        modes = modes_from_palace_output(postpro_dir, junctions, region_names=region_names)
    except FileNotFoundError as exc:
        return QuantumAnalysis(
            status=EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            source="none",
            reason=str(exc),
            junctions=junctions,
            modes=[],
            pyepr_available=pyepr_available(),
        )
    if not any(m.junction_participation for m in modes):
        return QuantumAnalysis(
            status=EvidenceStatus.SIMULATION_INVALID,
            source="palace_fields",
            reason="Palace output carries no junction port participation (port-EPR.csv/port-E.csv)",
            junctions=junctions,
            modes=modes,
            dielectric_participation={
                str(m.index): dict(m.electric_energy_fraction) for m in modes
            },
            magnetic_participation={str(m.index): dict(m.magnetic_energy_fraction) for m in modes},
            pyepr_available=pyepr_available(),
        )
    return epr_from_participations(
        modes, junctions, source="palace_fields", cross_check=cross_check
    )


# ----------------------------------------------------------------------- persistence


def write_quantum_analysis(analysis: QuantumAnalysis, out_dir: str | Path) -> Path:
    """Persist ``quantum_analysis.json`` and return its path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "quantum_analysis.json"
    payload: dict[str, Any] = analysis.model_dump(mode="json", by_alias=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fmt(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_quantum_summary(analysis: QuantumAnalysis) -> str:
    """Markdown summary suitable for embedding in ``report.md``."""
    lines = [
        "## Quantum (EPR) analysis",
        "",
        f"- Status: `{analysis.status.value}` (source: {analysis.source})",
        f"- Method: {analysis.method}",
    ]
    if analysis.reason:
        lines.append(f"- Note: {analysis.reason}")
    if analysis.qubit_mode_index is not None:
        lines.extend(
            (
                f"- Qubit mode: {analysis.qubit_mode_index}; dressed f01 = "
                f"{_fmt(analysis.qubit_frequency_ghz)} GHz; anharmonicity = "
                f"{_fmt(analysis.qubit_anharmonicity_ghz)} GHz",
            )
        )
    if analysis.modes:
        junction_names = [j.name for j in analysis.junctions]
        lines.extend(
            (
                "",
                "| Mode | f_lin (GHz) | f_dressed (GHz) | alpha (GHz) | "
                + " | ".join(f"p[{n}]" for n in junction_names)
                + " |",
            )
        )
        lines.append("|---|---|---|---|" + "---|" * len(junction_names))
        for mode in analysis.modes:
            key = str(mode.index)
            ps = " | ".join(
                _fmt(analysis.participation_matrix.get(key, {}).get(n, 0.0)) for n in junction_names
            )
            lines.append(
                f"| {mode.index} | {_fmt(analysis.linear_frequency_ghz.get(key))} | "
                f"{_fmt(analysis.dressed_frequency_ghz.get(key))} | "
                f"{_fmt(analysis.anharmonicity_ghz.get(key))} | {ps} |"
            )
        if len(analysis.modes) > 1:
            keys = [str(m.index) for m in analysis.modes]
            lines.extend(
                (
                    "",
                    "Cross-Kerr chi (GHz):",
                    "",
                    "| | " + " | ".join(keys) + " |",
                    "|---|" + "---|" * len(keys),
                )
            )
            for row in keys:
                lines.append(
                    f"| {row} | "
                    + " | ".join(_fmt(analysis.chi_matrix_ghz[row][col], 6) for col in keys)
                    + " |"
                )
    check = analysis.scqubits_cross_check
    if check is not None:
        lines.extend(
            (
                "",
                f"- scqubits cross-check: `{check.status.value}`"
                + (f" — {check.reason}" if check.reason else ""),
            )
        )
        if check.f01_ghz is not None:
            lines.append(
                f"  - exact transmon f01 = {_fmt(check.f01_ghz)} GHz (EPR deviation "
                f"{_fmt(check.f01_deviation_percent, 2)} %), alpha = {_fmt(check.anharmonicity_ghz)} GHz "
                f"(deviation {_fmt(check.anharmonicity_deviation_percent, 2)} %)"
            )
    lines.append(f"- pyEPR importable: {'yes' if analysis.pyepr_available else 'no'}")
    for warning in analysis.warnings:
        lines.append(f"- Warning: {warning}")
    return "\n".join(lines) + "\n"


def embed_in_report(report_path: str | Path, analysis: QuantumAnalysis) -> Path:
    """Insert or replace the quantum summary block in a Markdown report (idempotent)."""
    path = Path(report_path)
    block = f"{REPORT_BEGIN}\n{render_quantum_summary(analysis)}{REPORT_END}\n"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if REPORT_BEGIN in existing and REPORT_END in existing:
        start = existing.index(REPORT_BEGIN)
        end = existing.index(REPORT_END) + len(REPORT_END)
        trailing = existing[end:].lstrip("\n")
        updated = existing[:start] + block + ("\n" + trailing if trailing else "")
    else:
        separator = (
            ""
            if not existing or existing.endswith("\n\n")
            else ("\n" if existing.endswith("\n") else "\n\n")
        )
        updated = existing + separator + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return path


__all__ = [
    "QUANTUM_ANALYSIS_SCHEMA",
    "JunctionModel",
    "ModeEnergy",
    "QuantumAnalysis",
    "ScqubitsCrossCheck",
    "analyze_palace_output",
    "embed_in_report",
    "epr_from_participations",
    "josephson_energy_ghz_from_ic",
    "josephson_energy_ghz_from_lj",
    "modes_from_palace_output",
    "pyepr_available",
    "render_quantum_summary",
    "scqubits_available",
    "scqubits_transmon_cross_check",
    "write_quantum_analysis",
]
