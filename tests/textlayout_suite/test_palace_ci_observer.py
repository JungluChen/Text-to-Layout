"""Instrumentation checks only: these fixtures are never solver evidence."""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "observe_palace_ci.py"
spec = importlib.util.spec_from_file_location("palace_ci_observer", SCRIPT)
assert spec is not None and spec.loader is not None
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def test_tail_is_bounded_and_tolerates_partial_utf8(tmp_path: Path) -> None:
    path = tmp_path / "large.log"
    path.write_bytes(b"x" * 5000 + b"\xff\r\nlast line")
    result = observer.read_tail(path, 32)
    assert result["size_bytes"] == 5012
    assert result["truncated"] is True
    assert len(result["tail"]) <= 32
    assert result["tail"].endswith("\r\nlast line")
    assert "unavailable" in observer.read_tail(tmp_path / "absent")


def test_cgroup_membership_selects_own_group(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    # Model Linux procfs bytes, independent of the test host newline policy.
    (proc / "self/cgroup").write_bytes(b"0::/job\n")
    groups = tmp_path / "groups"
    (groups / "job").mkdir(parents=True)
    (groups / "job/memory.current").write_bytes(b"123\n")
    (groups / "memory.current").write_bytes(b"999\n")
    sample = observer.snapshot(tmp_path / "missing-run", proc=proc, cgroups=groups)
    assert sample["cgroup_memory"]["memory.current"]["tail"] == "123\n"
    assert "unavailable" in sample["files"]["base_mesh/palace.stdout.txt"]
    (proc / "self/cgroup").write_bytes(b"0::/../outside\n")
    assert "cgroup_unavailable" in observer.snapshot(tmp_path, proc=proc, cgroups=groups)


def test_once_retains_the_same_snapshot_it_streams(tmp_path: Path) -> None:
    output = tmp_path / "observations.txt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run", str(tmp_path / "not-started"),
         "--output", str(output), "--once"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    streamed = json.loads(result.stdout)
    assert streamed == json.loads(output.read_text())
    assert streamed["schema"] == "textlayout.palace-ci-observation.v1"
    assert not (tmp_path / "not-started").exists()


def test_invalid_interval_does_not_create_output(tmp_path: Path) -> None:
    output = tmp_path / "observations.txt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run", str(tmp_path), "--output", str(output),
         "--interval", "nan", "--once"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2
    assert not output.exists()


@pytest.mark.skipif(os.name == "nt", reason="Linux Actions Bash lifecycle contract")
@pytest.mark.parametrize("exit_code", [0, 7])
def test_observer_cleanup_preserves_benchmark_exit(tmp_path: Path, exit_code: int) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/palace-integration.yml").read_text())
    step = next(s for s in workflow["jobs"]["palace"]["steps"]
                if s.get("name") == "Run the reduced CPW quarter-wave benchmark")
    # YAML strips indentation. Replace only the actual benchmark with an inert
    # exit-code probe; this is a shell-lifecycle test, never solver evidence.
    prefix = step["run"].split("uv run textlayout simulate palace-resonator")[0]
    prefix = prefix.replace(".venv/bin/python", shlex.quote(sys.executable))
    prefix = prefix.replace("scripts/observe_palace_ci.py", shlex.quote(str(SCRIPT)))
    command = prefix + shlex.quote(sys.executable) + " -c " + shlex.quote(
        "from pathlib import Path; import time\n"
        "deadline = time.monotonic() + 8\n"
        "while not Path('out/toolchain/palace_runtime.txt').exists():\n"
        "    assert time.monotonic() < deadline, 'observer did not start'\n"
        "    time.sleep(0.05)\n"
        f"raise SystemExit({exit_code})"
    )
    result = subprocess.run(
        ["/bin/bash", "-e", "-c", command], cwd=tmp_path,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == exit_code
    assert (tmp_path / "out/toolchain/palace_runtime.txt").is_file()
