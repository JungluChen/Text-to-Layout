"""Read-only CI diagnostics; never launches, cancels, or validates a solver."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

TAIL_BYTES = 4096
OBSERVED_FILES = (
    "toolchain.json", "resource_decision.json", "run_manifest.json",
    "base_mesh/mesh_metrics.json", "base_mesh/palace_amr.json",
    "base_mesh/palace.stdout.txt", "base_mesh/palace.stderr.txt",
    "base_mesh/resource_summary.json", "base_mesh/resource_samples.json",
)


def read_tail(path: Path, limit: int = TAIL_BYTES) -> dict[str, object]:
    """Bound memory/log volume even when a running solver produces a large file."""
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            data = stream.read(limit)
        return {"size_bytes": size, "tail": data.decode("utf-8", errors="replace"),
                "truncated": size > limit}
    except OSError as exc:
        return {"unavailable": type(exc).__name__}


def snapshot(run: Path, *, proc: Path = Path("/proc"),
             cgroups: Path = Path("/sys/fs/cgroup")) -> dict[str, object]:
    sample: dict[str, object] = {
        "schema": "textlayout.palace-ci-observation.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "host/process diagnostics; not numerical validation",
        "meminfo": read_tail(proc / "meminfo"),
        "files": {name: read_tail(run / name) for name in OBSERVED_FILES},
    }
    try:
        paths = [line[3:] for line in (proc / "self/cgroup").read_text().splitlines()
                 if line.startswith("0::")]
        if len(paths) != 1 or ".." in Path(paths[0]).parts:
            raise ValueError("cgroup v2 membership unavailable")
        group = cgroups / paths[0].lstrip("/")
        sample["cgroup_path"] = paths[0]
        sample["cgroup_memory"] = {
            name: read_tail(group / name) for name in
            ("memory.current", "memory.peak", "memory.max", "memory.events")
        }
    except (OSError, ValueError) as exc:
        sample["cgroup_unavailable"] = type(exc).__name__
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid,ppid,rss,vsz,pcpu,comm"], capture_output=True,
            text=True, timeout=3, check=False,
        )
        if result.returncode:
            sample["processes_unavailable"] = f"ps exit {result.returncode}"
        else:
            rows = result.stdout.splitlines()[1:]
            rows.sort(key=lambda row: int(row.split()[2]), reverse=True)
            sample["process_columns"] = "pid ppid rss_KiB vsz_KiB cpu_percent command_name"
            sample["largest_processes"] = rows[:12]
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        sample["processes_unavailable"] = type(exc).__name__
    return sample


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as log:
        while True:
            line = json.dumps(snapshot(args.run), ensure_ascii=True)
            log.write(line + "\n")
            log.flush()
            # One JSON line escapes solver newlines; it is not a shell command.
            print(line, flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
