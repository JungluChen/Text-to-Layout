"""Local audit command recorder; artifacts stay in ignored out/audit/."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
name, *command = sys.argv[1:]
out = root / "out" / "audit" / "commands"
out.mkdir(parents=True, exist_ok=True)
start = time.time()
env = os.environ.copy()
env.setdefault("MPLCONFIGDIR", str(root / ".tools" / "matplotlib"))
env.setdefault("PYTHONHASHSEED", "0")
meta = {
    "command": command, "cwd": str(root), "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
    "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "platform": platform.platform(), "architecture": platform.machine(), "python": sys.version,
    "environment": {k: v for k, v in env.items() if k in {
        "MPLCONFIGDIR", "PYTHONHASHSEED", "PATH", "TEXTLAYOUT_FASTHENRY",
        "TEXTLAYOUT_FASTERCAP", "TEXTLAYOUT_OPENEMS", "TEXTLAYOUT_JOSIM"}},
    "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
}
with (out / f"{name}.log").open("wb") as log:
    result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
meta.update(exit_code=result.returncode, runtime_s=time.time()-start,
            log_sha256=hashlib.sha256((out / f"{name}.log").read_bytes()).hexdigest())
(out / f"{name}.json").write_text(json.dumps(meta, indent=2)+"\n")
print(json.dumps({k: meta[k] for k in ("command", "exit_code", "runtime_s")}, indent=2))
print((out / f"{name}.log").read_text(errors="replace")[-18000:])
sys.exit(result.returncode)
