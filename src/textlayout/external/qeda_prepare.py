"""Prepare the audited QEDA probe without importing or executing Node/QEDA."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_PROBE = b'''name: ProbeResistor
group: Resistor
keywords: resistor
pinout:
  L: 1
  R: 2
schematic:
  symbol: resistor
housing:
  pattern: custom
  bodyWidth: 2
  bodyLength: 1
  height: 0.5
  padWidth: 1
  padHeight: 1.5
  padPosition: -1.5, 0, 1.5, 0
'''
_EXPECTED_OUTPUTS = (
    'kicad/probe.lib', 'kicad/probe.dcm',
    'kicad/probe.pretty/Resistor_PROBERESISTOR.kicad_mod',
    'kicad/probe.3dshapes/Resistor_PROBERESISTOR.wrl',
)


@dataclass(frozen=True)
class PreparedQedaProbe:
    output_dir: Path
    manifest_path: Path
    manifest_sha256: str
    input_sha256: str
    script_sha256: str
    status: Literal['input_files_prepared'] = 'input_files_prepared'


def prepare_probe(output_dir: Path, *, runtime_package: Path) -> PreparedQedaProbe:
    """Write fixed inputs and a hash manifest into a new, exclusively created dir.

    Parent directory must exist and be trusted. Runtime path must be absolute;
    it is an unverified configuration value, not installation/provenance evidence.
    No runtime discovery, import, download, process execution or output assessment.
    An I/O failure leaves partial files for inspection; no successful manifest is
    returned. Existing directories/files/symlinks are never reused or removed.
    """
    runtime = str(runtime_package)
    if not runtime_package.is_absolute() or len(runtime) > 4096:
        raise ValueError('runtime_package must be an absolute path of at most 4096 characters')
    if any(ord(char) < 32 or ord(char) == 127 for char in runtime):
        raise ValueError('runtime_package contains a control character')
    # JSON string encoding prevents a configured path from becoming JS source.
    script = (
        'const Qeda = require(' + json.dumps(runtime, ensure_ascii=True) + ');\n'
        'const lib = new Qeda.Library();\n'
        'lib.add("probe");\n'
        'lib.generate("probe");\n'
    ).encode('ascii')
    input_hash = hashlib.sha256(_PROBE).hexdigest()
    script_hash = hashlib.sha256(script).hexdigest()
    manifest = (json.dumps({
        'schema': 'textlayout.qeda-preparation.v1',
        'status': 'input_files_prepared',
        'runtime_package': runtime,
        'required_qeda_version': '0.4.1',
        'runtime_identity_status': 'NOT_VERIFIED',
        'execution_status': 'NOT_EXECUTED',
        'reference_status': 'NOT_EVALUATED',
        'geometry_units': 'mm',
        'input_hashes': {'library/probe.yaml': input_hash, 'generate.cjs': script_hash},
        'expected_outputs': _EXPECTED_OUTPUTS,
    }, indent=2, sort_keys=True) + '\n').encode('utf-8')
    # Do not resolve first: a pre-existing symlink must fail exclusive creation.
    output_dir.mkdir(exist_ok=False)
    (output_dir / 'library').mkdir()
    with (output_dir / 'library/probe.yaml').open('xb') as stream:
        stream.write(_PROBE)
    with (output_dir / 'generate.cjs').open('xb') as stream:
        stream.write(script)
    manifest_path = output_dir / 'preparation.json'
    with manifest_path.open('xb') as stream:
        stream.write(manifest)
    return PreparedQedaProbe(
        output_dir=output_dir, manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        input_sha256=input_hash, script_sha256=script_hash,
    )
