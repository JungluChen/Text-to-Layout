"""A real Palace eigenmode adapter: detect, hash, configure, run, parse.

Palace (`awslabs/palace`) is an MPI finite-element solver. This module owns the
whole subprocess cycle and nothing else -- it computes no physics, and it makes
no claim about a result it did not read out of a file the solver wrote.

Three properties are load-bearing:

**Detection never lies.** When Palace is absent the adapter says so, with the
reason, and the caller emits ``SKIPPED_SOLVER_ABSENT``. There is no fallback
path that quietly produces a number.

**Identity is captured before the run, not asserted after it.** The executable is
hashed (or a container digest recorded), the version is probed, and the
configuration is serialised with sorted keys and hashed. Two runs that disagree
can therefore be told apart by their inputs rather than by argument.

**Parsing is strict.** The previous implementation scanned every CSV under the
output tree for any float in ``[1e6, 1e12]`` and called the first one a
frequency. That will read a mesh-quality statistic as a resonance. This parser
reads Palace's ``eig.csv`` by *column name*, rejects a non-finite entry rather
than skipping it, and fails loudly when the file is not what it claims to be.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.simulation.mesh_convergence import SolverIdentity
from textlayout.simulation.runners import _execution_command, find_executable

_WSL_PREFIX = "wsl:"

#: `palace --version` prints e.g. "Palace version: v0.16.0-34-gea2e7b23". The git
#: describe suffix is captured too: a release tag alone does not identify the
#: build, and 34 commits past v0.16.0 is not v0.16.0.
_VERSION_RE = re.compile(
    r"Palace\s+(?:version:?\s*)?\(?v?([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-[0-9]+-g[0-9a-f]+)?)",
    re.IGNORECASE,
)

#: Columns Palace writes into postpro/eig.csv. Matched loosely on whitespace and
#: braces because the exact spacing has changed between releases, but never
#: guessed positionally.
_EIG_INDEX = re.compile(r"^\s*m\s*$", re.IGNORECASE)
_EIG_REAL = re.compile(r"re\s*\{?\s*f\s*\}?.*ghz", re.IGNORECASE)
_EIG_IMAG = re.compile(r"im\s*\{?\s*f\s*\}?.*ghz", re.IGNORECASE)
_EIG_Q = re.compile(r"^\s*q\s*$", re.IGNORECASE)


class PalaceUnavailable(RuntimeError):
    """Palace could not be located. The caller must skip, never substitute."""


class PalaceOutputError(RuntimeError):
    """Palace ran but its output is not what it claims to be."""


@dataclass(frozen=True)
class PalaceCapability:
    """What is known about the Palace installation, before anything is run."""

    executable: str | None = None
    version: str | None = None
    executable_sha256: str | None = None
    container_digest: str | None = None
    mpi_launcher: str | None = None
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.executable is not None

    @property
    def identified(self) -> bool:
        """Whether the exact binary can be named from this record alone."""
        return bool(self.executable_sha256 or self.container_digest)

    def solver_identity(self, command: list[str]) -> SolverIdentity:
        return SolverIdentity(
            name="Palace",
            version=self.version,
            executable_sha256=self.executable_sha256,
            container_digest=self.container_digest,
            command=list(command),
        )

    def require(self) -> str:
        if self.executable is None:
            raise PalaceUnavailable(self.unavailable_reason or "Palace was not found")
        return self.executable


@dataclass(frozen=True)
class Eigenmode:
    """One converged eigenpair as Palace reported it."""

    index: int
    frequency_ghz: float
    #: Imaginary part; ``f = Re + i Im``. Loss makes this non-zero.
    frequency_imag_ghz: float | None = None
    quality_factor: float | None = None


@dataclass(frozen=True)
class PalaceRun:
    """A completed subprocess, with every artifact retained on disk."""

    command: list[str]
    return_code: int
    runtime_seconds: float
    stdout_path: Path
    stderr_path: Path
    output_dir: Path
    timed_out: bool = False
    output_files: dict[str, str] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0 and not self.timed_out


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wsl_exe() -> str:
    return shutil.which("wsl") or "wsl"


def _hash_executable(executable: str) -> str | None:
    """SHA-256 of the binary, whether it lives on this filesystem or inside WSL."""
    if executable.startswith(_WSL_PREFIX):
        target = executable.removeprefix(_WSL_PREFIX)
        try:
            completed = subprocess.run(
                [_wsl_exe(), "bash", "-lc", f"sha256sum {target!r}"],
                capture_output=True, text=True, timeout=120, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        token = completed.stdout.split(maxsplit=1)
        return token[0] if token and len(token[0]) == 64 else None
    path = Path(executable)
    return sha256_file(path) if path.is_file() else None


def _probe_version(executable: str) -> str | None:
    """Ask Palace what it is. ``None`` when it will not say -- never a guess."""
    for flags in (["--version"], ["--help"], ["-h"], []):
        command = _execution_command(executable, flags, Path.cwd())
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=120, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        match = _VERSION_RE.search(f"{completed.stdout}\n{completed.stderr}")
        if match:
            return match.group(1)
    return None


def detect_palace(
    explicit: str | None = None,
    *,
    container_digest: str | None = None,
    probe_version: bool = True,
) -> PalaceCapability:
    """Locate Palace and capture its identity, or explain why it is absent."""
    executable = find_executable(
        ("palace", "palace.exe"), explicit, env_var="TEXTLAYOUT_PALACE"
    )
    if executable is None:
        return PalaceCapability(
            unavailable_reason=(
                "Palace was not found on PATH, in .tools/, in WSL, or via "
                "TEXTLAYOUT_PALACE. Install it (https://awslabs.github.io/palace/) "
                "or point TEXTLAYOUT_PALACE at the binary."
            )
        )
    launcher = find_executable(("mpirun", "mpiexec"), None, env_var="TEXTLAYOUT_MPIRUN")
    return PalaceCapability(
        executable=executable,
        version=_probe_version(executable) if probe_version else None,
        executable_sha256=_hash_executable(executable),
        container_digest=container_digest,
        mpi_launcher=launcher,
    )


def write_config(config: dict[str, Any], path: Path) -> str:
    """Serialise deterministically and return the config's SHA-256.

    Sorted keys, fixed separators: the same configuration always produces the
    same bytes and the same hash, on any platform, in any Python.
    """
    payload = json.dumps(config, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    return hashlib.sha256(payload.encode()).hexdigest()


def run_palace(
    capability: PalaceCapability,
    config_path: Path,
    *,
    cwd: Path,
    timeout_seconds: int = 3600,
    processes: int = 1,
) -> PalaceRun:
    """Execute Palace once. Never raises on solver failure -- that is a result."""
    executable = capability.require()
    if processes > 1:
        if capability.mpi_launcher is None:
            raise PalaceUnavailable(
                f"{processes} processes requested but no mpirun/mpiexec was found"
            )
        arguments = ["-np", str(processes), _strip(executable), config_path.name]
        command = _execution_command(capability.mpi_launcher, arguments, cwd)
    else:
        command = _execution_command(executable, [config_path.name], cwd)

    stdout_path = cwd / "palace.stdout.txt"
    stderr_path = cwd / "palace.stderr.txt"
    started = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True,
            timeout=timeout_seconds, check=False,
        )
        stdout, stderr, return_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as expired:
        timed_out = True
        stdout = expired.stdout.decode() if isinstance(expired.stdout, bytes) else (expired.stdout or "")
        stderr = expired.stderr.decode() if isinstance(expired.stderr, bytes) else (expired.stderr or "")
        stderr += f"\n[textlayout] Palace exceeded its {timeout_seconds}s timeout and was killed.\n"
        return_code = -1
    runtime = time.perf_counter() - started

    stdout_path.write_text(stdout or "[textlayout] Palace emitted no stdout.\n", encoding="utf-8")
    stderr_path.write_text(stderr or "[textlayout] Palace emitted no stderr.\n", encoding="utf-8")

    return PalaceRun(
        command=list(command),
        return_code=return_code,
        runtime_seconds=runtime,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        output_dir=cwd,
        timed_out=timed_out,
    )


def _strip(executable: str) -> str:
    return executable.removeprefix(_WSL_PREFIX)


def _column(header: list[str], pattern: re.Pattern[str], what: str, source: Path) -> int:
    for index, name in enumerate(header):
        if pattern.search(name.strip()):
            return index
    raise PalaceOutputError(f"{source}: no {what} column in header {header!r}")


def parse_eigenmodes(eig_csv: Path) -> list[Eigenmode]:
    """Read Palace's eigenvalue table by column name.

    Refuses to skip a bad row. A non-finite eigenvalue is a fact about the solve
    and must reach the caller, not be silently dropped so the remaining rows look
    healthy.
    """
    if not eig_csv.is_file():
        raise PalaceOutputError(f"missing Palace eigenvalue output: {eig_csv}")
    with eig_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise PalaceOutputError(f"{eig_csv}: no eigenvalue rows")

    header = rows[0]
    index_column = _column(header, _EIG_INDEX, "mode index", eig_csv)
    real_column = _column(header, _EIG_REAL, "Re{f} (GHz)", eig_csv)
    imag_column = _optional_column(header, _EIG_IMAG)
    quality_column = _optional_column(header, _EIG_Q)

    modes: list[Eigenmode] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        frequency = _finite(row[real_column], eig_csv, "Re{f}")
        modes.append(
            Eigenmode(
                index=int(float(row[index_column])),
                frequency_ghz=frequency,
                frequency_imag_ghz=(
                    _finite(row[imag_column], eig_csv, "Im{f}") if imag_column is not None else None
                ),
                quality_factor=(
                    _finite(row[quality_column], eig_csv, "Q") if quality_column is not None else None
                ),
            )
        )
    if not modes:
        raise PalaceOutputError(f"{eig_csv}: header present but no eigenvalues")
    return modes


def _optional_column(header: list[str], pattern: re.Pattern[str]) -> int | None:
    for index, name in enumerate(header):
        if pattern.search(name.strip()):
            return index
    return None


def _finite(cell: str, source: Path, what: str) -> float:
    try:
        value = float(cell)
    except ValueError as exc:
        raise PalaceOutputError(f"{source}: {what} is not a number: {cell!r}") from exc
    if value != value or value in (float("inf"), float("-inf")):
        raise PalaceOutputError(f"{source}: {what} is not finite: {value!r}")
    return value


def parse_domain_energy(domain_csv: Path, *, mode: int = 1) -> dict[int, float]:
    """Electric-field energy per named domain index, for **one** eigenmode.

    ``domain-E.csv`` carries one row per eigenmode. ``mode`` selects it by the
    ``m`` column; it is not the row position. Reading a fixed row -- the last,
    say -- silently reports a different mode's energy whenever the number of
    requested modes changes, which is exactly the participation of the wrong
    resonance.

    Energies are returned, not participations: normalising is the caller's
    decision, and a caller that cannot see the total cannot check that it sums
    to one.
    """
    if not domain_csv.is_file():
        raise PalaceOutputError(f"missing Palace domain energy output: {domain_csv}")
    with domain_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise PalaceOutputError(f"{domain_csv}: no domain energy rows")

    header = [cell.strip() for cell in rows[0]]
    mode_column = _column(header, _EIG_INDEX, "mode index", domain_csv)
    selected: list[str] | None = None
    available: list[int] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        index = int(float(row[mode_column]))
        available.append(index)
        if index == mode:
            selected = row
    if selected is None:
        raise PalaceOutputError(
            f"{domain_csv}: no energy row for mode {mode}; the file carries modes {available}"
        )

    energies: dict[int, float] = {}
    for index, name in enumerate(header):
        match = re.search(r"E_elec\s*\[\s*(\d+)\s*\]", name, re.IGNORECASE)
        if match:
            energies[int(match.group(1))] = _finite(selected[index], domain_csv, name)
    if not energies:
        raise PalaceOutputError(
            f"{domain_csv}: no per-domain E_elec columns; enable "
            "Domains.Postprocessing.Energy in the Palace configuration"
        )
    return energies
