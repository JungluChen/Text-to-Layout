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
    PALACE_ROOT,
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

WSL_CACHE = "$HOME/.cache/textlayout-palace"
INSTALL_STDOUT = ROOT / "out" / "toolchain" / "palace_install.stdout.txt"
INSTALL_STDERR = ROOT / "out" / "toolchain" / "palace_install.stderr.txt"


def _tool() -> dict[str, object]:
    return next(tool for tool in load_registry().tools if tool["id"] == "palace")


def _checkout_script(name: str, url: str, commit: str) -> str:
    target = f'"{WSL_CACHE}/{name}"'
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
    clone = "; ".join(
        [
            "set -euo pipefail",
            f"mkdir -p {WSL_CACHE}",
            _checkout_script("spack", "https://github.com/spack/spack.git", SPACK_COMMIT),
            _checkout_script(
                "spack-packages",
                "https://github.com/spack/spack-packages.git",
                SPACK_PACKAGES_COMMIT,
            ),
            f"grep -q 'version(\"{PALACE_VERSION}\"' "
            f'"{WSL_CACHE}/spack-packages/repos/spack_repo/builtin/packages/palace/package.py" || '
            f"sed -i '/version(\"develop\"/a\\    version(\"{PALACE_VERSION}\", "
            f"tag=\"v{PALACE_VERSION}\", commit=\"{PALACE_COMMIT}\")' "
            f'"{WSL_CACHE}/spack-packages/repos/spack_repo/builtin/packages/palace/package.py"',
        ]
    )
    bootstrapped = run_wsl(clone, timeout=1800)
    if bootstrapped.returncode != 0:
        raise RuntimeError(bootstrapped.stdout + bootstrapped.stderr)
    committed_environment = windows_to_wsl(SPACK_ENV / "spack.yaml")
    install_store = windows_to_wsl(PALACE_ROOT / "spack-opt")
    spack = f"{WSL_CACHE}/spack"
    packages = f"{WSL_CACHE}/spack-packages/repos/spack_repo/builtin"
    config = f"{WSL_CACHE}/config"
    environment = f"{WSL_CACHE}/environment"
    script = "; ".join(
        [
            "set -euo pipefail",
            f"export SPACK_USER_CONFIG_PATH={config}",
            f"rm -rf {environment}; mkdir -p {environment}",
            f"cp {shlex_quote(committed_environment)} {environment}/spack.yaml",
            f". {spack}/share/spack/setup-env.sh",
            f"spack repo add --scope site {packages} >/dev/null 2>&1 || true",
            "spack compiler find /usr/bin >/dev/null",
            f"spack -e {environment} config add config:install_tree:root:{install_store}",
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
        "spack_runtime_cache": WSL_CACHE,
        "compiler_and_mpi_tail": completed.stdout.splitlines()[-8:],
        "installed_at": timestamp(),
    }


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
