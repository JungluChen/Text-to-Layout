#!/usr/bin/env python
"""One-command simulator bootstrap: JoSIM, FasterCap, then PSCAN2, then WRspice.

Usage (or via ``make setup-simulators``)::

    python scripts/bootstrap_simulators.py [--detect-only] [--strict] [--tools-dir DIR]

Policy:

- JoSIM is the primary circuit backend and the only one this script tries to
  install automatically (official MIT-licensed release artifact, else source
  build, else exact manual steps).
- FasterCap is required for IDC capacitance extraction. On Windows, this
  script prefers building it inside WSL Ubuntu; native Windows compilation is
  only attempted manually with a matching GCC+wxWidgets toolchain.
- PSCAN2 and WRspice are detected and documented; their absence never blocks
  JoSIM setup or the normal workflow.
- Nothing here fakes availability: the final table comes from
  ``scripts/check_simulators.py`` and every claim is re-verified by actually
  running the executables.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import check_simulators as checker
import install_josim
import install_pscan2
import install_wrspice


_TEXTLAYOUT_PATCH_BEGIN = "# TEXTLAYOUT LOCAL PATCH BEGIN"
_TEXTLAYOUT_PATCH_END = "# TEXTLAYOUT LOCAL PATCH END"


def apply_textlayout_local_patch_to_fastercap_cmakelists(contents: str) -> str:
    if _TEXTLAYOUT_PATCH_BEGIN in contents and _TEXTLAYOUT_PATCH_END in contents:
        return contents

    updated = contents
    updated = updated.replace(
        "# In this case, we pass the options `wx-config --version=3.0 --static=no --debug`,",
        "# In this local patch, we stop forcing a wxWidgets version and use the active `wx-config` installation.",
    )
    updated = updated.replace(
        "set(wxWidgets_CONFIG_OPTIONS --version=3.0 --static=no $<$<CONFIG:Debug>:--debug>)",
        f"{_TEXTLAYOUT_PATCH_BEGIN}\nset(wxWidgets_CONFIG_OPTIONS --static=no $<$<CONFIG:Debug>:--debug>)",
    )
    if "set(WXWIDGETS_LIBS ${WXWIDGETS_LIBS} ${wxWidgets_LIBRARIES})" in updated:
        wx_block = (
            "\n"
            "if(NOT DEFINED TEXTLAYOUT_WX_CONFIG_LIBS)\n"
            "    if(NOT DEFINED wxWidgets_CONFIG_EXECUTABLE)\n"
            "        find_program(wxWidgets_CONFIG_EXECUTABLE wx-config)\n"
            "    endif()\n"
            "    if(DEFINED wxWidgets_CONFIG_EXECUTABLE)\n"
            "        execute_process(\n"
            "            COMMAND ${wxWidgets_CONFIG_EXECUTABLE} --libs std,core,base\n"
            "            OUTPUT_VARIABLE TEXTLAYOUT_WX_CONFIG_LIBS_RAW\n"
            "            OUTPUT_STRIP_TRAILING_WHITESPACE\n"
            "        )\n"
            "        if(TEXTLAYOUT_WX_CONFIG_LIBS_RAW)\n"
            "            separate_arguments(TEXTLAYOUT_WX_CONFIG_LIBS NATIVE_COMMAND \"${TEXTLAYOUT_WX_CONFIG_LIBS_RAW}\")\n"
            "        endif()\n"
            "    endif()\n"
            "endif()\n"
        )
        updated = updated.replace(
            "set(WXWIDGETS_LIBS ${WXWIDGETS_LIBS} ${wxWidgets_LIBRARIES})",
            "set(WXWIDGETS_LIBS ${WXWIDGETS_LIBS} ${wxWidgets_LIBRARIES})" + wx_block,
        )

    updated = updated.replace(
        "target_link_libraries(FasterCap ${EXTRA_LIBS} ${WXWIDGETS_LIBS} ${EIGEN_LIBS} ${wxWidgets_LIBRARIES})",
        "target_link_libraries(FasterCap ${EXTRA_LIBS} ${WXWIDGETS_LIBS} ${TEXTLAYOUT_WX_CONFIG_LIBS} ${EIGEN_LIBS} ${wxWidgets_LIBRARIES})\n"
        + _TEXTLAYOUT_PATCH_END,
    )
    return updated


def ensure_fastercap_local_patch(tools_dir: Path) -> None:
    cmake = tools_dir / "FasterCap" / "CMakeLists.txt"
    if not cmake.is_file():
        return
    backup = cmake.with_name("CMakeLists.txt.textlayout.bak")
    if not backup.exists():
        backup.write_text(cmake.read_text(encoding="utf-8"), encoding="utf-8")
    original = cmake.read_text(encoding="utf-8")
    updated = apply_textlayout_local_patch_to_fastercap_cmakelists(original)
    if updated != original:
        cmake.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")


def _diagnose_fastercap_failure(stdout: str, stderr: str) -> str:
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    unresolved = (
        "undefined reference to wxTheAssertHandler",
        "undefined reference to wxOnAssert",
        "undefined reference to wxTrapInAssert",
    )
    if any(symbol in combined for symbol in unresolved):
        return (
            "FASTER_CAP_BUILD_FAILED: wxWidgets link failed (unresolved wx symbols). "
            "Ensure wx-config is present and CMake links `wx-config --libs std,core,base`."
        )
    if "FASTER_CAP_BUILD_FAILED:" in combined:
        for line in reversed(combined.splitlines()):
            if "FASTER_CAP_BUILD_FAILED:" in line:
                return line.strip()
    tail = combined.splitlines()[-12:]
    tail_text = "\n".join(tail).strip()
    return f"FASTER_CAP_BUILD_FAILED: WSL build failed.\n{tail_text}" if tail_text else "FASTER_CAP_BUILD_FAILED: WSL build failed."


def _record_fastercap(
    tools_dir: Path,
    status: str,
    *,
    path: str | None = None,
    reason: str | None = None,
    method: str | None = None,
    version: str | None = None,
) -> None:
    checker.write_manifest_entry(
        tools_dir,
        "fastercap",
        {
            "status": status,
            "path": path,
            "method": method,
            "version": version,
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )


def _windows_to_wsl(path: Path) -> str:
    resolved = str(path.resolve())
    if len(resolved) >= 2 and resolved[1] == ":":
        drive = resolved[0].lower()
        rest = resolved[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return resolved.replace("\\", "/")


def _wsl_run(command: str, *, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl.exe", "-e", "bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _extract_fastercap_version(output: str) -> str | None:
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("FasterCap version "):
            return text
        if text.startswith("FasterCap "):
            return text
    return None


def _run_wsl_fastercap_probe(
    fastercap_dir_wsl: str, command: str, *, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return _wsl_run(
        f"cd {fastercap_dir_wsl} && {command}",
        timeout=timeout,
    )


def _verify_wsl_fastercap_binary(fastercap_dir_wsl: str, binary_path: str) -> tuple[str, str] | None:
    file_probe = _run_wsl_fastercap_probe(fastercap_dir_wsl, f"file {binary_path}", timeout=30)
    file_output = "\n".join(part for part in (file_probe.stdout, file_probe.stderr) if part).strip()
    if file_probe.returncode != 0 or "ELF" not in file_output or "relocatable" in file_output:
        return None

    for command in (
        f"{binary_path} --help",
        f"{binary_path} -h",
        binary_path,
    ):
        probe = _run_wsl_fastercap_probe(fastercap_dir_wsl, command, timeout=60)
        combined = "\n".join(part for part in (probe.stdout, probe.stderr) if part)
        version = _extract_fastercap_version(combined)
        if version is not None:
            return (file_output, version)
    return None


def _verify_existing_wsl_fastercap(tools_dir: Path) -> tuple[str, str] | None:
    fastercap_dir_wsl = _windows_to_wsl(tools_dir / "FasterCap")
    verified = _verify_wsl_fastercap_binary(fastercap_dir_wsl, "./bin/FasterCap")
    if verified is None:
        return None
    _, version = verified
    return (f"{fastercap_dir_wsl}/bin/FasterCap", version)


def ensure_fastercap(tools_dir: Path, *, detect_only: bool = False) -> checker.Detection:
    detection = checker.detect_fastercap(tools_dir)
    if detection.available:
        detection.version = detection.version or checker.capture_version(detection.path or "")
        detection.status = checker.STATUS_READY
        _record_fastercap(
            tools_dir,
            "ready",
            path=detection.path,
            method=detection.method,
            version=detection.version,
        )
        return detection

    if platform.system() == "Windows":
        ensure_fastercap_local_patch(tools_dir)
        if shutil.which("wsl.exe") is not None:
            verified_existing = _verify_existing_wsl_fastercap(tools_dir)
            if verified_existing is not None:
                installed_path, version = verified_existing
                _record_fastercap(
                    tools_dir,
                    "ready",
                    path=installed_path,
                    method="wsl-existing",
                    version=version,
                    reason="WSL FasterCap binary verified; run FasterCap from Ubuntu/WSL.",
                )
                detection = checker.detect_fastercap(tools_dir)
                detection.version = version
                detection.status = checker.STATUS_READY
                return detection

    if detect_only:
        _record_fastercap(
            tools_dir,
            "manual_install_required",
            reason="FasterCap not found; run this script without --detect-only to attempt WSL/Linux build.",
        )
        return detection

    if platform.system() == "Windows":
        if shutil.which("wsl.exe") is None:
            _record_fastercap(
                tools_dir,
                "manual_install_required",
                reason="WSL is not available; install WSL Ubuntu or build FasterCap with GCC+wxWidgets on Windows.",
            )
            print(
                "\n[fastercap] WSL not found. Recommended path:\n"
                "  1) Install WSL + Ubuntu\n"
                "  2) In Ubuntu:\n"
                "     sudo apt-get update\n"
                "     sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git file\n"
            )
            return detection

        sudo_probe = _wsl_run("if sudo -n true 2>/dev/null; then echo OK; else echo NO; fi", timeout=30)
        if sudo_probe.returncode != 0 or "OK" not in (sudo_probe.stdout or ""):
            reason = "WSL sudo requires a password; run the following commands manually in Ubuntu."
            _record_fastercap(tools_dir, "manual_install_required", reason=reason, method="wsl-manual")
            repo_root = tools_dir.parent
            repo_root_wsl = _windows_to_wsl(repo_root)
            print(
                "\n[fastercap] sudo requires a password; run manually in Ubuntu:\n"
                "  sudo apt-get update\n"
                "  sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git file\n"
                f"  cd {repo_root_wsl}\n"
                "  cd .tools/FasterCap\n"
                "  rm -rf build\n"
                "  wx_config=$(command -v wx-config)\n"
                "  echo \"wx-config: $wx_config\"\n"
                "  wx_cxxflags=\"$($wx_config --cxxflags)\"\n"
                "  wx_libs=\"$($wx_config --libs std,core,base)\"\n"
                "  echo \"wx-config --cxxflags: $wx_cxxflags\"\n"
                "  echo \"wx-config --libs std,core,base: $wx_libs\"\n"
                "  cmake -S . -B build -DFASTFIELDSOLVERS_HEADLESS=ON -DCMAKE_BUILD_TYPE=Release "
                "-DwxWidgets_CONFIG_EXECUTABLE=\"$wx_config\" -DCMAKE_CXX_FLAGS=\"$wx_cxxflags\"\n"
                "  cmake --build build -j\"$(nproc)\"\n"
                "  exe=$(find build -type f -perm -111 ! -name '*.o' ! -name '*.a' \\( -name 'FasterCap' -o -name 'fastercap' \\) | head -n 1)\n"
                "  echo \"Built: $exe\"\n"
                "  test -n \"$exe\" || { echo \"FASTER_CAP_BUILD_FAILED: no executable found\"; exit 2; }\n"
                "  file \"$exe\"\n"
                "  file \"$exe\" | grep -q \"ELF\" || { echo \"FASTER_CAP_BUILD_FAILED: built file is not an ELF executable\"; exit 2; }\n"
                "  file \"$exe\" | grep -q \"relocatable\" && { echo \"FASTER_CAP_BUILD_FAILED: built file is an object/relocatable, not an executable\"; exit 2; }\n"
                "  mkdir -p bin\n"
                "  cp -f \"$exe\" bin/FasterCap\n"
                "  chmod +x bin/FasterCap\n"
                "  file bin/FasterCap\n"
                "  file bin/FasterCap | grep -q \"ELF\" || { echo \"FASTER_CAP_BUILD_FAILED: built file is not an ELF executable\"; exit 2; }\n"
                "  file bin/FasterCap | grep -q \"relocatable\" && { echo \"FASTER_CAP_BUILD_FAILED: built file is an object/relocatable, not an executable\"; exit 2; }\n"
                "  tmp_output=$(mktemp)\n"
                "  if ./bin/FasterCap --help >\"$tmp_output\" 2>&1 || ./bin/FasterCap -h >\"$tmp_output\" 2>&1 || ./bin/FasterCap >\"$tmp_output\" 2>&1; then true; fi\n"
                "  grep -q \"FasterCap version \" \"$tmp_output\" || { sed -n '1,20p' \"$tmp_output\"; echo \"FASTER_CAP_BUILD_FAILED: help/version invocation failed\"; rm -f \"$tmp_output\"; exit 2; }\n"
                "  sed -n '1,4p' \"$tmp_output\"\n"
                "  rm -f \"$tmp_output\"\n"
            )
            return detection

        print("[fastercap] installing WSL build dependencies (apt-get)")
        install = _wsl_run(
            "set -euo pipefail; sudo apt-get update; sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git file",
            timeout=3600,
        )
        if install.returncode != 0:
            _record_fastercap(
                tools_dir,
                "install_failed",
                reason=(install.stderr or install.stdout or "").strip()[-500:],
                method="wsl-apt-get",
            )
            print("\n[fastercap] apt-get failed:\n" + (install.stdout or "") + (install.stderr or ""))
            return detection

        repo_root = tools_dir.parent
        src_wsl = _windows_to_wsl(tools_dir / "FasterCap")
        build_cmd = (
            "set -euo pipefail; "
            f"cd {src_wsl}; "
            "wx_config=$(command -v wx-config || true); "
            "test -n \"$wx_config\" || { echo \"FASTER_CAP_BUILD_FAILED: wx-config not found\"; exit 2; }; "
            "wx_cxxflags=\"$($wx_config --cxxflags)\"; "
            "wx_libs=\"$($wx_config --libs std,core,base)\"; "
            "echo \"wx-config: $wx_config\"; "
            "echo \"wx-config --cxxflags: $wx_cxxflags\"; "
            "echo \"wx-config --libs std,core,base: $wx_libs\"; "
            "rm -rf build; "
            "cmake -S . -B build -DFASTFIELDSOLVERS_HEADLESS=ON -DCMAKE_BUILD_TYPE=Release "
            "-DwxWidgets_CONFIG_EXECUTABLE=\"$wx_config\" -DCMAKE_CXX_FLAGS=\"$wx_cxxflags\"; "
            "cmake --build build -j\"$(nproc)\"; "
            "exe=$(find build -type f -perm -111 ! -name '*.o' ! -name '*.a' \\( -name 'FasterCap' -o -name 'fastercap' \\) | head -n 1); "
            "test -n \"$exe\" || { echo \"FASTER_CAP_BUILD_FAILED: no executable found\"; exit 2; }; "
            "file \"$exe\"; "
            "file \"$exe\" | grep -q \"ELF\" || { echo \"FASTER_CAP_BUILD_FAILED: built file is not an ELF executable\"; exit 2; }; "
            "file \"$exe\" | grep -q \"relocatable\" && { echo \"FASTER_CAP_BUILD_FAILED: built file is an object/relocatable, not an executable\"; exit 2; }; "
            "mkdir -p bin; "
            "cp -f \"$exe\" bin/FasterCap; "
            "chmod +x bin/FasterCap; "
            "file bin/FasterCap"
        )
        print("[fastercap] building FasterCap in WSL")
        built = _wsl_run(build_cmd, timeout=7200)
        if built.returncode != 0:
            _record_fastercap(
                tools_dir,
                "install_failed",
                reason=_diagnose_fastercap_failure(built.stdout or "", built.stderr or ""),
                method="wsl-build",
            )
            print("\n[fastercap] build failed:\n" + (built.stdout or "") + (built.stderr or ""))
            return detection

        verified = _verify_wsl_fastercap_binary(src_wsl, "./bin/FasterCap")
        if verified is None:
            _record_fastercap(
                tools_dir,
                "install_failed",
                reason="FASTER_CAP_BUILD_FAILED: help/version invocation failed after copying bin/FasterCap",
                method="wsl-verify",
            )
            print("\n[fastercap] verification failed: bin/FasterCap did not pass file/help checks")
            return detection

        _, version = verified
        installed_path = f"{src_wsl}/bin/FasterCap"
        _record_fastercap(
            tools_dir,
            "ready",
            path=installed_path,
            method="wsl-build",
            version=version,
            reason="WSL build; run FasterCap from Ubuntu/WSL (Linux executable).",
        )
        detection = checker.detect_fastercap(tools_dir)
        detection.version = version
        detection.status = checker.STATUS_READY
        return detection

    if platform.system() == "Linux":
        _record_fastercap(
            tools_dir,
            "manual_install_required",
            reason=(
                "Install build prerequisites and build FasterCap. "
                "Example (Ubuntu): sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git"
            ),
        )
        print(
            "\n[fastercap] Linux build prerequisites (Ubuntu):\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git\n"
            "  cd .tools/FasterCap\n"
            "  rm -rf build\n"
            "  cmake -S . -B build -DFASTFIELDSOLVERS_HEADLESS=ON -DCMAKE_BUILD_TYPE=Release\n"
            "  cmake --build build -j\"$(nproc)\"\n"
        )
        return detection

    _record_fastercap(
        tools_dir,
        "manual_install_required",
        reason="Unsupported platform for automated FasterCap install; use WSL/Linux or provide TEXTLAYOUT_FASTERCAP.",
    )
    return detection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools-dir", default=None)
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only detect; never download, build, or print install walls of text.",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    tools_dir = Path(args.tools_dir) if args.tools_dir else checker.default_tools_dir()

    print("=" * 70)
    print("textlayout simulator bootstrap")
    print(f"  platform : {platform.platform()}")
    print(f"  machine  : {platform.machine()}")
    print(f"  python   : {platform.python_version()} ({sys.executable})")
    print(f"  tools dir: {tools_dir}")
    print(f"  strict   : {strict}")
    print("=" * 70)

    print("\n--- [1/4] JoSIM (primary) " + "-" * 42)
    josim = install_josim.ensure_josim(tools_dir, detect_only=args.detect_only)

    print("\n--- [2/4] FasterCap (capacitance extraction) " + "-" * 23)
    fastercap = ensure_fastercap(tools_dir, detect_only=args.detect_only)

    print("\n--- [3/4] PSCAN2 (optional) " + "-" * 40)
    install_pscan2.ensure_pscan2(tools_dir, detect_only=args.detect_only)

    print("\n--- [4/4] WRspice (optional) " + "-" * 39)
    install_wrspice.ensure_wrspice(tools_dir, detect_only=args.detect_only)

    print("\n--- summary " + "-" * 56)
    checker_args = ["--tools-dir", str(tools_dir)]
    if strict:
        checker_args.append("--strict")
    exit_code = checker.main(checker_args)

    print("\nNext commands:")
    print("  make check-simulators")
    print("  make demo-jpa")
    if not josim.available:
        print(
            "\nNote: JoSIM is not available; demos will still run and honestly "
            "report SKIPPED_SOLVER_ABSENT for circuit checks."
        )
    if fastercap.status != checker.STATUS_READY:
        print(
            "\nNote: FasterCap is not available; IDC extraction will stop at "
            "EXTRACTION_INPUT_PREPARED and never claim CAPACITANCE_EXTRACTED."
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
