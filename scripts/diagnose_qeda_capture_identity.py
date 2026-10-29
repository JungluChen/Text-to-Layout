"""Collect metadata failures without changing capture decisions or claiming acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from textlayout.external import qeda_capture as capture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    original = capture._identity
    events: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    failure_count = 0

    def record(info):
        value = original(info)
        events.append(dict(zip(
            ('device', 'inode', 'size', 'mtime_ns', 'ctime_ns'), value, strict=True,
        ), mode=info.st_mode))
        return value

    with patch.object(capture, '_identity', record):
        for iteration in range(1000):
            events.clear()
            with tempfile.TemporaryDirectory() as name:
                root = Path(name)
                (root / 'node_modules').mkdir()
                (root / 'node_modules' / 'z').write_bytes(b'payload')
                (root / 'package.json').write_text('excluded')
                try:
                    first = capture.capture_inventory(root)
                    second = capture.capture_inventory(root)
                    if first != second:
                        raise ValueError('unchanged captures differ')
                except (OSError, ValueError) as exc:
                    failure_count += 1
                    if len(failures) < 20:
                        failures.append({
                            'iteration': iteration, 'type': type(exc).__name__,
                            'error': str(exc), 'identity_events': list(events),
                        })
    result = {
        'schema': 'textlayout.qeda-identity-diagnostic.v1',
        'status': 'ANOMALY_OBSERVED' if failure_count else 'NOT_REPRODUCED',
        'platform': platform.platform(), 'python': sys.version,
        'iterations': 1000, 'captures_per_successful_iteration': 2,
        'failure_count': failure_count, 'retained_failure_limit': 20,
        'failures': failures,
        'source_sha256': hashlib.sha256(Path(capture.__file__).read_bytes()).hexdigest(),
        'limitations': 'Temporary regular-file diagnostic only; no runtime or scientific acceptance.',
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as output:
        output.write(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
