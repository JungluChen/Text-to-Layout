#!/usr/bin/env python
"""Install or detect JoSIM (the primary circuit-simulation backend).

Strategy, in order (stdlib only, never fakes success):

1. Detect: ``TEXTLAYOUT_JOSIM`` → ``.tools/josim/bin/josim-cli`` →
   ``.tools/josim/bin/josim`` → PATH ``josim-cli`` → PATH ``josim``.
2. Normalise: an existing ``.tools/josim-*/bin/josim-cli*`` (e.g. a manually
   unpacked release) is copied into the canonical ``.tools/josim/bin/``.
3. Official release artifact: JoSIM is MIT-licensed; download the
   platform-matching asset from github.com/JoeyDelp/JoSIM releases and
   extract it into ``.tools/josim/``.
4. Source build (Linux/macOS): git + CMake + compiler; prints the exact
   package-manager commands when prerequisites are missing.
5. Windows fallback: print exact manual steps; do not fail unless strict.

Every attempt is verified by running the executable and recorded in
``.tools/simulators.json``. ``TEXTLAYOUT_STRICT_SIMULATORS=1`` (or
``--strict``) turns "could not install" into a nonzero exit.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

import check_simulators as checker

RELEASE_API = "https://api.github.com/repos/JoeyDelp/JoSIM/releases/latest"
SOURCE_REPO = "https://github.com/JoeyDelp/JoSIM"

#: (platform.system(), normalised machine) → asset-name fragment.
_ASSET_KEYS = {
    ("Windows", "x86_64"): "windows-x64",
    ("Linux", "x86_64"): "linux-x64",
    ("Linux", "aarch64"): "linux-arm64",
    ("Darwin", "x86_64"): "macos-x64",
    ("Darwin", "aarch64"): "macos-arm64",
}

_LINUX_PREREQ_HINTS = {
    "git": "sudo apt-get install -y git   (or: sudo dnf install git)",
    "cmake": "sudo apt-get install -y cmake   (or: sudo dnf install cmake)",
    "c++": "sudo apt-get install -y build-essential   (or: sudo dnf groupinstall 'Development Tools')",
    "make": "sudo apt-get install -y make ninja-build",
}


def _machine() -> str:
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x86_64"
    if machine in ("arm64", "aarch64"):
        return "aarch64"
    return machine


def _record(tools_dir: Path, status: str, *, path: str | None = None, reason: str | None = None,
            method: str | None = None, version: str | None = None) -> None:
    checker.write_manifest_entry(
        tools_dir,
        "josim",
        {
            "status": status,
            "path": path,
            "method": method,
            "version": version,
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )


def _verify(executable: Path) -> str | None:
    """Run the freshly installed binary; return its banner or None."""
    return checker.capture_version(str(executable))


def _install_from_bin_dir(source_bin: Path, tools_dir: Path) -> Path | None:
    """Copy a discovered josim-cli (plus siblings) into .tools/josim/bin/."""
    target_bin = tools_dir / "josim" / "bin"
    target_bin.mkdir(parents=True, exist_ok=True)
    installed: Path | None = None
    for item in source_bin.iterdir():
        if not item.is_file():
            continue
        destination = target_bin / item.name
        shutil.copy2(item, destination)
        if item.name.startswith("josim-cli") or (
            installed is None and item.name.startswith("josim")
        ):
            installed = destination
    if installed is not None and os.name != "nt":
        installed.chmod(0o755)
    return installed


def _normalise_existing(tools_dir: Path) -> Path | None:
    """Adopt a manually unpacked release like .tools/josim-v2.7/bin/."""
    if not tools_dir.is_dir():
        return None
    for candidate in sorted(tools_dir.glob("josim-*")):
        bin_dir = candidate / "bin"
        if not bin_dir.is_dir():
            continue
        if any(item.name.startswith("josim") for item in bin_dir.iterdir() if item.is_file()):
            print(f"[josim] adopting existing install from {bin_dir}")
            return _install_from_bin_dir(bin_dir, tools_dir)
    return None


def _download_release(tools_dir: Path) -> Path | None:
    """Fetch the platform-matching official release asset (MIT-licensed)."""
    key = _ASSET_KEYS.get((platform.system(), _machine()))
    if key is None:
        print(f"[josim] no known release asset for {platform.system()}/{_machine()}")
        return None
    try:
        with urllib.request.urlopen(RELEASE_API, timeout=30) as response:
            release = json.load(response)
    except OSError as exc:
        print(f"[josim] could not query GitHub releases: {exc}")
        return None
    asset = next(
        (item for item in release.get("assets", []) if key in item.get("name", "")), None
    )
    if asset is None:
        print(f"[josim] release {release.get('tag_name')} has no asset matching '{key}'")
        return None
    build_dir = tools_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    archive = build_dir / asset["name"]
    print(f"[josim] downloading {asset['name']} ({asset['size']} bytes)")
    try:
        urllib.request.urlretrieve(asset["browser_download_url"], archive)
    except OSError as exc:
        print(f"[josim] download failed: {exc}")
        return None
    extract_dir = build_dir / "josim-release"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extract_dir)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(extract_dir)
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"[josim] extraction failed: {exc}")
        return None
    for candidate in extract_dir.rglob("josim-cli*"):
        if candidate.is_file():
            return _install_from_bin_dir(candidate.parent, tools_dir)
    print("[josim] extracted archive did not contain a josim-cli executable")
    return None


def _missing_build_tools() -> list[str]:
    missing = []
    if shutil.which("git") is None:
        missing.append("git")
    if shutil.which("cmake") is None:
        missing.append("cmake")
    if not any(shutil.which(cc) for cc in ("c++", "g++", "clang++")):
        missing.append("c++")
    if not any(shutil.which(tool) for tool in ("make", "ninja")):
        missing.append("make")
    return missing


def _build_from_source(tools_dir: Path) -> Path | None:
    """git clone + CMake build into .tools/build/ (Linux/macOS path)."""
    missing = _missing_build_tools()
    if missing:
        print("[josim] cannot build from source; missing tools:")
        for tool in missing:
            print(f"  - {tool}: {_LINUX_PREREQ_HINTS.get(tool, 'install via your package manager')}")
        return None
    build_root = tools_dir / "build"
    source_dir = build_root / "JoSIM"
    build_root.mkdir(parents=True, exist_ok=True)
    try:
        if not source_dir.is_dir():
            subprocess.run(
                ["git", "clone", "--depth", "1", SOURCE_REPO, str(source_dir)],
                check=True,
                timeout=600,
            )
        subprocess.run(
            ["cmake", "-B", "build", "-DCMAKE_BUILD_TYPE=Release", "."],
            cwd=source_dir,
            check=True,
            timeout=600,
        )
        subprocess.run(
            ["cmake", "--build", "build", "--parallel", "--config", "Release"],
            cwd=source_dir,
            check=True,
            timeout=3600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[josim] source build failed: {exc}")
        print("[josim] see docs/simulators/troubleshooting.md (section: JoSIM build failed)")
        return None
    for candidate in (source_dir / "build").rglob("josim-cli*"):
        if candidate.is_file() and candidate.suffix in ("", ".exe"):
            return _install_from_bin_dir(candidate.parent, tools_dir)
    print("[josim] build completed but josim-cli was not found under build/")
    return None


def _print_windows_manual_steps() -> None:
    print(
        "\n[josim] automatic install did not succeed. Manual steps (Windows):\n"
        "  1. Download JoSIM-<ver>-windows-x64.zip from "
        "https://github.com/JoeyDelp/JoSIM/releases\n"
        "  2. Extract it so that josim-cli.exe sits at .tools\\josim\\bin\\josim-cli.exe\n"
        "     (any folder works if you set the environment variable instead)\n"
        "  3. Or set: $env:TEXTLAYOUT_JOSIM = 'C:\\path\\to\\josim-cli.exe'\n"
        "  4. Re-run: python scripts/check_simulators.py\n"
    )


def ensure_josim(tools_dir: Path, *, detect_only: bool = False) -> checker.Detection:
    """Detect JoSIM, installing it if needed. Never raises; always records."""
    detection = checker.detect_josim(tools_dir)
    if detection.available:
        detection.version = detection.version or checker.capture_version(detection.path or "")
        _record(
            tools_dir,
            checker.STATUS_READY,
            path=detection.path,
            method=detection.method,
            version=detection.version,
        )
        print(f"[josim] ready ({detection.method}): {detection.path}")
        return detection
    if detect_only:
        print("[josim] not detected (detect-only mode; no install attempted)")
        return detection

    installed = _normalise_existing(tools_dir)
    if installed is None:
        installed = _download_release(tools_dir)
    if installed is None and platform.system() != "Windows":
        installed = _build_from_source(tools_dir)

    if installed is not None:
        version = _verify(installed)
        if version:
            _record(
                tools_dir,
                checker.STATUS_READY,
                path=str(installed),
                method="installed",
                version=version,
            )
            print(f"[josim] installed and verified: {installed} ({version})")
            return checker.detect_josim(tools_dir)
        _record(
            tools_dir,
            checker.STATUS_INSTALL_FAILED,
            path=str(installed),
            reason="installed binary did not answer --version/--help",
        )
        print(f"[josim] installed file did not verify: {installed}")
        return checker.detect_josim(tools_dir)

    if platform.system() == "Windows":
        _print_windows_manual_steps()
    _record(
        tools_dir,
        checker.STATUS_INSTALL_FAILED,
        reason="no release asset usable and source build unavailable/failed",
    )
    return checker.detect_josim(tools_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools-dir", default=None)
    parser.add_argument("--detect-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    tools_dir = Path(args.tools_dir) if args.tools_dir else checker.default_tools_dir()
    detection = ensure_josim(tools_dir, detect_only=args.detect_only)
    if not detection.available:
        print("[josim] NOT available; the workflow will honestly report SKIPPED_SOLVER_ABSENT")
        if strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
