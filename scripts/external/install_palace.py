"""Install pinned Palace 0.17.0 with Spack under the git-ignored .tools tree."""

from __future__ import annotations

import argparse
import json
import os
import sys

from _common import download_archive, load_registry
from _palace_common import (
    GMESH_VERSION,
    INSTALL_RECORD,
    INSTALL_REPORT,
    PALACE_COMMIT,
    PALACE_VERSION,
    ROOT,
    SPACK_COMMIT,
    SPACK_ENV,
    SPACK_PACKAGES_COMMIT,
    SPACK_VERSION,
    gmsh_identity,
    palace_install_identity,
    run_wsl,
    shlex_quote,
    timestamp,
    verify_palace_archive,
    windows_to_wsl,
    write_json,
)

INSTALL_STDOUT = ROOT / "out" / "toolchain" / "palace_install.stdout.txt"
INSTALL_STDERR = ROOT / "out" / "toolchain" / "palace_install.stderr.txt"


def _tool() -> dict[str, object]:
    return next(tool for tool in load_registry().tools if tool["id"] == "palace")


def _native_root() -> str:
    """Resolve the native WSL ext4 root for the whole Spack tree.

    The Spack clone, environment, caches, transient build stage, and the
    installed binaries all live here. Native ext4 is required for viable
    performance: on the /mnt/c 9p mount, the many-small-file operations of
    autotools configure and package installs (gettext installs ~1,760 tiny
    .po files; MFEM/PETSc install thousands of headers) take an order of
    magnitude longer and stall. The pinned *source archives* and the
    install-identity record (install.json) remain under the git-ignored
    .tools/ tree; the binaries here are git-ignored, outside src/, and fully
    reproducible from those pinned sources. Override with
    ``TEXTLAYOUT_PALACE_NATIVE_ROOT``.
    """
    override = os.environ.get("TEXTLAYOUT_PALACE_NATIVE_ROOT")
    if override:
        return override.rstrip("/")
    probe = run_wsl('printf "%s" "$HOME"', timeout=60)
    home = probe.stdout.strip().splitlines()[-1].strip() if probe.returncode == 0 else ""
    base = home if home.startswith("/") else "/tmp"
    return f"{base}/.cache/textlayout-palace"


def _checkout_script(cache: str, name: str, url: str, commit: str) -> str:
    target = f'"{cache}/{name}"'
    return (
        f"if [ -d {target}/.git ] && "
        f"git -C {target} rev-parse HEAD | grep -qx {commit}; then :; "
        f"else rm -rf {target}; mkdir -p {target}; "
        f"git -C {target} init; "
        f"git -C {target} remote add origin {shlex_quote(url)}; "
        f"git -C {target} fetch --depth 1 origin {commit}; "
        f"git -C {target} checkout --detach FETCH_HEAD; fi; "
        f"git -C {target} rev-parse HEAD | grep -qx {commit}"
    )


def _spack_install() -> dict[str, object]:
    native_root = _native_root()
    wsl_cache = native_root
    clone = "; ".join(
        [
            "set -euo pipefail",
            f"mkdir -p {shlex_quote(wsl_cache)}",
            _checkout_script(
                wsl_cache, "spack", "https://github.com/spack/spack.git", SPACK_COMMIT
            ),
            _checkout_script(
                wsl_cache,
                "spack-packages",
                "https://github.com/spack/spack-packages.git",
                SPACK_PACKAGES_COMMIT,
            ),
            f"grep -q 'version(\"{PALACE_VERSION}\"' "
            f'"{wsl_cache}/spack-packages/repos/spack_repo/builtin/packages/palace/package.py" || '
            f"sed -i '/version(\"develop\"/a\\    version(\"{PALACE_VERSION}\", "
            f"tag=\"v{PALACE_VERSION}\", commit=\"{PALACE_COMMIT}\")' "
            f'"{wsl_cache}/spack-packages/repos/spack_repo/builtin/packages/palace/package.py"',
        ]
    )
    bootstrapped = run_wsl(clone, timeout=1800)
    if bootstrapped.returncode != 0:
        raise RuntimeError(bootstrapped.stdout + bootstrapped.stderr)
    committed_environment = windows_to_wsl(SPACK_ENV / "spack.yaml")
    install_store = f"{native_root}/spack-opt"
    spack = f"{wsl_cache}/spack"
    packages = f"{wsl_cache}/spack-packages/repos/spack_repo/builtin"
    config = f"{wsl_cache}/config"
    environment = f"{wsl_cache}/environment"
    user_cache = f"{wsl_cache}/user-cache"
    source_cache = f"{wsl_cache}/source-cache"
    build_stage = f"{native_root}/build-stage"
    script = "; ".join(
        [
            "set -euo pipefail",
            f"export SPACK_USER_CONFIG_PATH={config}",
            f"export SPACK_USER_CACHE_PATH={user_cache}",
            f"rm -rf {environment}; mkdir -p {environment} {source_cache} "
            f"{shlex_quote(build_stage)}",
            f"cp {shlex_quote(committed_environment)} {environment}/spack.yaml",
            f". {spack}/share/spack/setup-env.sh",
            f"spack repo add --scope site {packages} >/dev/null 2>&1 || true",
            "spack compiler find /usr/bin >/dev/null",
            f"spack -e {environment} config add config:install_tree:root:{install_store}",
            f"spack -e {environment} config add 'config:source_cache:{source_cache}'",
            f"spack -e {environment} config add "
            f"'config:build_stage:[{build_stage}]'",
            f"spack -e {environment} concretize -f",
            f"spack -e {environment} install --fail-fast --use-buildcache=auto",
            "gcc --version | head -1",
            "g++ --version | head -1",
            "gfortran --version | head -1",
            "mpirun --version | head -2",
        ]
    )
    completed = run_wsl(script, timeout=4 * 3600)
    INSTALL_STDOUT.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_STDOUT.write_text(completed.stdout, encoding="utf-8")
    INSTALL_STDERR.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Spack Palace installation failed with {completed.returncode}; "
            f"see {INSTALL_STDOUT} and {INSTALL_STDERR}"
        )
    location = run_wsl(
        "; ".join(
            [
                "set -euo pipefail",
                f"export SPACK_USER_CONFIG_PATH={config}",
                f"export SPACK_USER_CACHE_PATH={user_cache}",
                f". {spack}/share/spack/setup-env.sh",
                f"spack -e {environment} location -i palace@{PALACE_VERSION}",
            ]
        ),
        timeout=300,
    )
    if location.returncode != 0:
        raise RuntimeError("Spack installed Palace but its prefix could not be resolved")
    prefix = location.stdout.strip().splitlines()[-1]
    executable = f"{prefix}/bin/palace"
    identity = run_wsl(
        f"{shlex_quote(executable)} --version; sha256sum {shlex_quote(executable)}",
        timeout=120,
    )
    digest = identity.stdout.strip().splitlines()[-1].split()[0]
    if PALACE_VERSION not in identity.stdout or len(digest) != 64:
        raise RuntimeError("installed Palace identity could not be verified")
    return {
        "status": "INSTALLED",
        "strategy": "pinned_spack_wsl",
        "palace_version": PALACE_VERSION,
        "palace_commit": PALACE_COMMIT,
        "palace_executable": f"wsl:{executable}" if os.name == "nt" else executable,
        "palace_executable_sha256": digest,
        "spack_version": SPACK_VERSION,
        "spack_commit": SPACK_COMMIT,
        "spack_packages_commit": SPACK_PACKAGES_COMMIT,
        "spack_environment": str((SPACK_ENV / "spack.yaml").relative_to(ROOT)),
        "spack_runtime_cache": wsl_cache,
        "install_tree": install_store,
        "build_stage": build_stage,
        "compiler_and_mpi_tail": completed.stdout.splitlines()[-8:],
        "installed_at": timestamp(),
    }


def _toolchain_versions() -> dict[str, object]:
    """Probe the live WSL MPI launcher and compiler versions."""
    probe = run_wsl(
        "; ".join(
            [
                "mpirun --version 2>/dev/null | head -1 || true",
                "gcc --version 2>/dev/null | head -1 || true",
                "g++ --version 2>/dev/null | head -1 || true",
                "gfortran --version 2>/dev/null | head -1 || true",
            ]
        ),
        timeout=120,
    )
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    mpi = next((line for line in lines if "mpi" in line.lower() or "open mpi" in line.lower()), "")
    return {
        "mpi_version": mpi,
        "compiler_versions": {
            "gcc": next((line for line in lines if line.lower().startswith("gcc")), ""),
            "gxx": next((line for line in lines if line.lower().startswith("g++")), ""),
            "gfortran": next(
                (line for line in lines if "fortran" in line.lower()), ""
            ),
        },
    }


def _git_commit() -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


def _enrich_identity(report: dict[str, object]) -> None:
    """Flatten the report to the documented palace_install.json schema.

    Adds the top-level identity fields (gmsh_version, mpi_version,
    compiler_versions, native_root, source_archive_*, git_commit) so the
    committed installation report is self-describing whether the install was
    freshly built or reused.
    """
    gmsh = report.get("gmsh") or {}
    archive = report.get("source_archive") or {}
    report.setdefault("gmsh_version", gmsh.get("version") if isinstance(gmsh, dict) else None)
    report.setdefault(
        "native_root",
        report.get("spack_runtime_cache") or _native_root(),
    )
    if isinstance(archive, dict):
        report.setdefault("source_archive_path", archive.get("path"))
        report.setdefault("source_archive_sha256", archive.get("sha256"))
    report.update(_toolchain_versions())
    report["git_commit"] = _git_commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="reinstall a valid installation")
    args = parser.parse_args()
    report: dict[str, object] = {
        "schema": "textlayout.palace-install.v1",
        "requested_version": PALACE_VERSION,
        "gmsh": gmsh_identity(),
        "source_archive": verify_palace_archive(),
    }
    try:
        tool = _tool()
        download_archive(tool)
        report["source_archive"] = verify_palace_archive()
        if not report["source_archive"]["available"]:  # type: ignore[index]
            raise RuntimeError("pinned Palace source archive failed SHA-256 verification")
        if report["gmsh"].get("version") != GMESH_VERSION:  # type: ignore[union-attr]
            raise RuntimeError(
                f"Gmsh {GMESH_VERSION} is required; run uv sync --all-extras first"
            )
        existing = None if args.force else palace_install_identity()
        if existing is not None:
            report.update(existing)
            report["reused"] = True
        else:
            report.update(_spack_install())
            report["reused"] = False
        if report.get("status") == "INSTALLED":
            _enrich_identity(report)
        write_json(INSTALL_RECORD, report)
        write_json(INSTALL_REPORT, report)
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        report.update({"status": "ABSENT", "error": str(exc), "failed_at": timestamp()})
        write_json(INSTALL_REPORT, report)
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
