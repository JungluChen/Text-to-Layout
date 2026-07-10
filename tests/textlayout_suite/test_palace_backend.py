"""The Palace adapter: detection, identity capture, execution, strict parsing.

The parser is the point. Its predecessor scanned every CSV under the output tree
for the first float in [1e6, 1e12] and called it a frequency -- which will read a
mesh-quality statistic as a resonance. This one reads Palace's eig.csv by column
name and refuses a row it cannot trust.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from textlayout.simulation.mesh_convergence import SolverIdentity
from textlayout.simulation.palace_backend import (
    Eigenmode,
    PalaceCapability,
    PalaceOutputError,
    PalaceUnavailable,
    detect_palace,
    parse_domain_energy,
    parse_eigenmodes,
    run_palace,
    write_config,
)

EIG_HEADER = "               m,   Re{f} (GHz),   Im{f} (GHz),              Q,   Error (Bkwd.)\n"


def _write_eig(path: Path, rows: str, header: str = EIG_HEADER) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + rows, encoding="utf-8")
    return path


def _fake_palace(tmp_path: Path, body: str) -> Path:
    """A stand-in Palace. Never used in a production path -- only here."""
    script = tmp_path / "fake_palace_impl.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        shim = tmp_path / "fake_palace.bat"
        shim.write_text(f'@echo off\n"{sys.executable}" "{script}" %1\n', encoding="ascii")
    else:
        shim = tmp_path / "fake_palace.sh"
        shim.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}" "$1"\n', encoding="ascii")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return shim


_WRITES_EIG = """
import pathlib, sys
out = pathlib.Path("postpro"); out.mkdir(exist_ok=True)
(out / "eig.csv").write_text(
    "               m,   Re{f} (GHz),   Im{f} (GHz),              Q\\n"
    "               1,   6.012345678,   1.00000e-05,      3.0000e+05\\n"
    "               2,   8.500000000,   2.00000e-05,      2.0000e+05\\n"
)
print("Palace (v0.16.0) finished")
"""


class TestDetection:
    def test_absent_palace_reports_why_and_never_pretends(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "textlayout.simulation.palace_backend.find_executable", lambda *a, **k: None
        )
        capability = detect_palace()
        assert capability.available is False
        assert capability.executable is None
        assert "not found" in (capability.unavailable_reason or "")

    def test_require_raises_rather_than_substituting(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "textlayout.simulation.palace_backend.find_executable", lambda *a, **k: None
        )
        with pytest.raises(PalaceUnavailable, match="not found"):
            detect_palace().require()

    def test_a_located_binary_is_hashed(self, tmp_path: Path, monkeypatch) -> None:
        binary = tmp_path / "palace"
        binary.write_bytes(b"not really palace")
        monkeypatch.setattr(
            "textlayout.simulation.palace_backend.find_executable",
            lambda names, explicit=None, **k: str(binary) if "palace" in names else None,
        )
        capability = detect_palace(probe_version=False)
        assert capability.available is True
        assert capability.executable_sha256 is not None
        assert len(capability.executable_sha256) == 64
        assert capability.identified is True

    def test_an_unhashed_unversioned_binary_is_not_identified(self) -> None:
        capability = PalaceCapability(executable="/usr/bin/palace")
        assert capability.available is True
        assert capability.identified is False

    def test_the_version_regex_matches_the_real_palace_banner(self) -> None:
        """Captured from `palace --version` of the 0.16 container used here."""
        from textlayout.simulation.palace_backend import _VERSION_RE

        match = _VERSION_RE.search("Palace version: v0.16.0-34-gea2e7b23")
        assert match is not None
        # The git-describe suffix is part of the identity: 34 commits past a
        # release tag is not that release.
        assert match.group(1) == "0.16.0-34-gea2e7b23"

    def test_a_plain_release_version_also_matches(self) -> None:
        from textlayout.simulation.palace_backend import _VERSION_RE

        assert _VERSION_RE.search("Palace (v0.13.0)").group(1) == "0.13.0"  # type: ignore[union-attr]

    def test_the_solver_identity_carries_the_container_digest(self) -> None:
        capability = PalaceCapability(
            executable="palace", version="0.16.0", container_digest="sha256:" + "a" * 64
        )
        identity = capability.solver_identity(["palace", "config.json"])
        assert isinstance(identity, SolverIdentity)
        assert identity.is_reproducible is True
        assert identity.name == "Palace"


class TestDeterministicConfiguration:
    def test_the_same_configuration_hashes_the_same(self, tmp_path: Path) -> None:
        config = {"Solver": {"Order": 2}, "Model": {"Mesh": "m.msh"}}
        reordered = {"Model": {"Mesh": "m.msh"}, "Solver": {"Order": 2}}
        first = write_config(config, tmp_path / "a.json")
        second = write_config(reordered, tmp_path / "b.json")
        assert first == second
        assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()

    def test_a_changed_configuration_changes_the_hash(self, tmp_path: Path) -> None:
        first = write_config({"Solver": {"Order": 2}}, tmp_path / "a.json")
        second = write_config({"Solver": {"Order": 3}}, tmp_path / "b.json")
        assert first != second

    def test_config_is_written_with_lf_endings(self, tmp_path: Path) -> None:
        write_config({"a": 1}, tmp_path / "c.json")
        assert b"\r\n" not in (tmp_path / "c.json").read_bytes()


class TestExecution:
    def test_a_successful_run_retains_stdout_stderr_and_returncode(self, tmp_path: Path) -> None:
        shim = _fake_palace(tmp_path, _WRITES_EIG)
        capability = PalaceCapability(executable=str(shim), version="0.16.0")
        write_config({"Problem": {"Type": "Eigenmode"}}, tmp_path / "palace.json")

        run = run_palace(capability, tmp_path / "palace.json", cwd=tmp_path, timeout_seconds=120)

        assert run.succeeded is True
        assert run.return_code == 0
        assert run.stdout_path.is_file() and run.stderr_path.is_file()
        assert "Palace" in run.stdout_path.read_text(encoding="utf-8")
        assert run.runtime_seconds > 0

    def test_a_failing_run_is_a_result_not_an_exception(self, tmp_path: Path) -> None:
        shim = _fake_palace(tmp_path, "import sys; sys.exit(3)")
        capability = PalaceCapability(executable=str(shim))
        write_config({}, tmp_path / "palace.json")

        run = run_palace(capability, tmp_path / "palace.json", cwd=tmp_path, timeout_seconds=120)
        assert run.succeeded is False
        assert run.return_code == 3
        assert run.timed_out is False

    def test_a_hanging_run_is_killed_and_marked_timed_out(self, tmp_path: Path) -> None:
        shim = _fake_palace(tmp_path, "import time; time.sleep(30)")
        capability = PalaceCapability(executable=str(shim))
        write_config({}, tmp_path / "palace.json")

        run = run_palace(capability, tmp_path / "palace.json", cwd=tmp_path, timeout_seconds=2)
        assert run.timed_out is True
        assert run.succeeded is False
        assert "timeout" in run.stderr_path.read_text(encoding="utf-8").lower()

    def test_mpi_is_refused_when_no_launcher_exists(self, tmp_path: Path) -> None:
        capability = PalaceCapability(executable="palace", mpi_launcher=None)
        write_config({}, tmp_path / "palace.json")
        with pytest.raises(PalaceUnavailable, match="no mpirun/mpiexec"):
            run_palace(capability, tmp_path / "palace.json", cwd=tmp_path, processes=4)

    def test_running_without_palace_raises(self, tmp_path: Path) -> None:
        write_config({}, tmp_path / "palace.json")
        with pytest.raises(PalaceUnavailable):
            run_palace(PalaceCapability(), tmp_path / "palace.json", cwd=tmp_path)


class TestStrictEigenmodeParsing:
    def test_columns_are_found_by_name_not_position(self, tmp_path: Path) -> None:
        path = _write_eig(
            tmp_path / "postpro" / "eig.csv",
            "               1,   6.012345678,   1.00000e-05,      3.0000e+05,  1e-9\n",
        )
        modes = parse_eigenmodes(path)
        assert modes == [
            Eigenmode(index=1, frequency_ghz=6.012345678, frequency_imag_ghz=1e-05, quality_factor=3.0e05)
        ]

    def test_a_reordered_header_still_parses_correctly(self, tmp_path: Path) -> None:
        path = _write_eig(
            tmp_path / "postpro" / "eig.csv",
            "6.5,1,2.0e-5\n",
            header="Re{f} (GHz),m,Im{f} (GHz)\n",
        )
        modes = parse_eigenmodes(path)
        assert modes[0].index == 1 and modes[0].frequency_ghz == 6.5

    def test_a_nan_eigenvalue_is_raised_not_skipped(self, tmp_path: Path) -> None:
        """The all-NaN Touchstone, in eigenmode form."""
        path = _write_eig(tmp_path / "postpro" / "eig.csv", "1,nan,0.0,1e5\n")
        with pytest.raises(PalaceOutputError, match="not finite"):
            parse_eigenmodes(path)

    def test_an_infinite_eigenvalue_is_raised(self, tmp_path: Path) -> None:
        path = _write_eig(tmp_path / "postpro" / "eig.csv", "1,inf,0.0,1e5\n")
        with pytest.raises(PalaceOutputError, match="not finite"):
            parse_eigenmodes(path)

    def test_a_missing_frequency_column_fails_loudly(self, tmp_path: Path) -> None:
        path = _write_eig(tmp_path / "postpro" / "eig.csv", "1,2,3\n", header="m,alpha,beta\n")
        with pytest.raises(PalaceOutputError, match=r"no Re\{f\}"):
            parse_eigenmodes(path)

    def test_a_header_with_no_rows_fails(self, tmp_path: Path) -> None:
        """Exactly what an OOM-killed Palace leaves behind: a header, no result.

        Observed for real at N=48 (795,024 DOF), which the kernel killed after
        508s. A parser that shrugged at this would report "no modes found" and
        let the convergence study silently drop a level.
        """
        path = _write_eig(tmp_path / "postpro" / "eig.csv", "")
        with pytest.raises(PalaceOutputError, match="no eigenvalue rows"):
            parse_eigenmodes(path)

    def test_a_missing_file_fails(self, tmp_path: Path) -> None:
        with pytest.raises(PalaceOutputError, match="missing Palace eigenvalue output"):
            parse_eigenmodes(tmp_path / "postpro" / "eig.csv")

    def test_a_decoy_csv_cannot_be_mistaken_for_the_eigenvalue_table(
        self, tmp_path: Path
    ) -> None:
        """The old parser read any float in [1e6, 1e12] from any CSV in the tree."""
        postpro = tmp_path / "postpro"
        postpro.mkdir()
        (postpro / "mesh-stats.csv").write_text("elements,dofs\n1000000,5000000\n", encoding="utf-8")
        with pytest.raises(PalaceOutputError, match="missing Palace eigenvalue output"):
            parse_eigenmodes(postpro / "eig.csv")

    def test_a_lossless_solve_has_no_quality_factor_column(self, tmp_path: Path) -> None:
        path = _write_eig(tmp_path / "postpro" / "eig.csv", "1,6.0\n", header="m,Re{f} (GHz)\n")
        modes = parse_eigenmodes(path)
        assert modes[0].quality_factor is None
        assert modes[0].frequency_imag_ghz is None


class TestDomainEnergyParsing:
    #: One row per eigenmode, as Palace writes it.
    THREE_MODES = (
        "m,E_elec[1] (J),E_elec[2] (J),E_mag (J)\n"
        "1,0.75,0.25,1.0\n"
        "2,0.40,0.60,1.0\n"
        "3,0.10,0.90,1.0\n"
    )

    def test_per_domain_electric_energy_is_read_by_index(self, tmp_path: Path) -> None:
        path = tmp_path / "domain-E.csv"
        path.write_text("m,E_elec[1] (J),E_elec[2] (J),E_mag (J)\n1,0.75,0.25,1.0\n", encoding="utf-8")
        assert parse_domain_energy(path) == {1: 0.75, 2: 0.25}

    def test_the_mode_is_selected_by_its_index_not_its_row_position(self, tmp_path: Path) -> None:
        """Reading a fixed row reports a different mode whenever N changes."""
        path = tmp_path / "domain-E.csv"
        path.write_text(self.THREE_MODES, encoding="utf-8")
        assert parse_domain_energy(path, mode=1) == {1: 0.75, 2: 0.25}
        assert parse_domain_energy(path, mode=3) == {1: 0.10, 2: 0.90}

    def test_the_fundamental_is_the_default_not_the_last_row(self, tmp_path: Path) -> None:
        path = tmp_path / "domain-E.csv"
        path.write_text(self.THREE_MODES, encoding="utf-8")
        assert parse_domain_energy(path) == parse_domain_energy(path, mode=1)

    def test_an_absent_mode_names_the_modes_that_are_present(self, tmp_path: Path) -> None:
        path = tmp_path / "domain-E.csv"
        path.write_text(self.THREE_MODES, encoding="utf-8")
        with pytest.raises(PalaceOutputError, match=r"no energy row for mode 7.*\[1, 2, 3\]"):
            parse_domain_energy(path, mode=7)

    def test_energies_are_returned_unnormalised(self, tmp_path: Path) -> None:
        """A caller that cannot see the total cannot check that it sums to one."""
        path = tmp_path / "domain-E.csv"
        path.write_text("m,E_elec[1] (J),E_elec[2] (J)\n1,3.0,1.0\n", encoding="utf-8")
        assert sum(parse_domain_energy(path).values()) == 4.0

    def test_a_solve_without_domain_postprocessing_fails_loudly(self, tmp_path: Path) -> None:
        path = tmp_path / "domain-E.csv"
        path.write_text("m,E_mag (J)\n1,1.0\n", encoding="utf-8")
        with pytest.raises(PalaceOutputError, match="Domains.Postprocessing.Energy"):
            parse_domain_energy(path)

    def test_a_non_finite_energy_is_raised(self, tmp_path: Path) -> None:
        path = tmp_path / "domain-E.csv"
        path.write_text("m,E_elec[1] (J)\n1,nan\n", encoding="utf-8")
        with pytest.raises(PalaceOutputError, match="not finite"):
            parse_domain_energy(path)
