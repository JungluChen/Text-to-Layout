import subprocess
import sys
from pathlib import Path

from textlayout.simulation.resource_sampler import (
    ProcessTreeResourceWatcher,
    evaluate_resource_budget,
)


def test_resource_budget_rejects_impossible_rss(tmp_path: Path) -> None:
    decision = evaluate_resource_budget(
        tmp_path,
        configured_max_rss_bytes=2**63 - 1,
    )
    assert decision.allowed is False
    assert decision.blockers


def test_resource_watcher_terminates_memory_consumer(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; payload=bytearray(64*1024*1024); time.sleep(30)",
        ]
    )
    watcher = ProcessTreeResourceWatcher(
        process.pid,
        max_rss_bytes=16 * 1024**2,
        event_path=tmp_path / "resource_limit_event.json",
    )
    result = watcher.run_until_exit()
    process.wait(timeout=5)
    assert result["resource_limit_terminated"] is True
    assert result["orphan_process_remaining"] is False
    assert (tmp_path / "resource_limit_event.json").is_file()
