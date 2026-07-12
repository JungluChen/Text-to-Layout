"""Install pinned ParaView by isolated administrative MSI extraction."""

from __future__ import annotations

import json
import subprocess
import urllib.request

from _paraview_common import (
    BINARY_SHA256,
    BINARY_SIZE,
    BINARY_URL,
    INSTALL_RECORD,
    INSTALL_REPORT,
    MSI,
    PREFIX,
    VERSION,
    identity,
    write_json,
)
from _common import sha256_file


def main() -> int:
    MSI.parent.mkdir(parents=True, exist_ok=True)
    if not MSI.is_file():
        urllib.request.urlretrieve(BINARY_URL, MSI)
    digest = sha256_file(MSI)
    if digest != BINARY_SHA256 or MSI.stat().st_size != BINARY_SIZE:
        raise SystemExit("ParaView MSI checksum or size mismatch")
    existing = identity()
    if existing is None:
        log = MSI.parent / "install.log"
        completed = subprocess.run(
            [
                "msiexec.exe",
                "/a",
                str(MSI),
                "/qn",
                f"TARGETDIR={PREFIX}",
                "/L*v",
                str(log),
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(f"ParaView extraction failed: {completed.returncode}")
    installed = identity()
    if installed is None or installed["version"] != VERSION:
        raise SystemExit("ParaView identity verification failed after extraction")
    payload = {
        "schema": "textlayout.paraview-install.v1",
        **installed,
        "binary_url": BINARY_URL,
        "binary_sha256": digest,
        "binary_size_bytes": MSI.stat().st_size,
        "prefix": str(PREFIX.resolve()),
    }
    write_json(INSTALL_RECORD, payload)
    write_json(INSTALL_REPORT, payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
