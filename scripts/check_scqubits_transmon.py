"""Fixed ideal-transmon benchmark; execution is not physical validation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "references/scqubits/transmon-plan.json"
PLAN_SHA256 = "d371af78e1c15b7cac4a15e28af57e12e7c4391e1fca51bbe24dbd23a48a4afd"


def assess(rows, reference, plan):
    """Reject missing/nonfinite evidence; assess only the locked numerical scope."""
    if [r['ncut'] for r in rows] != plan['cutoffs']:
        raise ValueError('Missing or reordered cutoffs')
    if len(reference) != plan['levels']:
        raise ValueError('Incomplete reference')
    for row in rows:
        if len(row['levels_hz']) != plan['levels']:
            raise ValueError('Incomplete spectrum')
        values = row['levels_hz'] + [row['scaled_residual']]
        if not all(math.isfinite(v) for v in values) or row['scaled_residual'] < 0:
            raise ValueError('Nonfinite or negative residual evidence')
        if row['levels_hz'][0] != 0 or any(b <= a for a, b in zip(row['levels_hz'], row['levels_hz'][1:])):
            raise ValueError('Invalid excitation spectrum')
    if not all(math.isfinite(v) for v in reference):
        raise ValueError('Nonfinite reference')
    metrics = {
        'last_refinement_hz': max(abs(a-b) for a,b in zip(rows[-1]['levels_hz'], rows[-2]['levels_hz'])),
        'reference_difference_hz': max(abs(a-b) for a,b in zip(rows[-1]['levels_hz'], reference)),
        'scaled_residual': max(r['scaled_residual'] for r in rows),
    }
    passed = (metrics['last_refinement_hz'] <= plan['max_refinement_hz']
              and metrics['reference_difference_hz'] <= plan['max_reference_hz']
              and metrics['scaled_residual'] <= plan['max_scaled_residual'])
    return metrics, passed


def execute(plan, out):
    import numpy as np
    import scqubits
    from scipy.special import mathieu_a, mathieu_b
    from textlayout.solvers.scqubits_adapter import execute_scqubits, prepare_scqubits_input

    source = Path(scqubits.__file__).parent / 'core/transmon.py'
    raw_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    normalized_hash = hashlib.sha256(source.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    if scqubits.__version__ != plan['version'] or normalized_hash != plan['source_sha256']:
        raise ValueError('Unaudited scqubits version/source')
    result = {'schema':'textlayout.scqubits-benchmark.v1', 'scope':plan['scope'],
              'versions':{p:importlib.metadata.version(p) for p in ('scqubits','numpy','scipy')},
              'platform':platform.platform(), 'python':platform.python_version(),
              'source_sha256':raw_hash, 'plan_sha256':PLAN_SHA256, 'cases':[]}
    h, e = 6.62607015e-34, 1.602176634e-19
    for i, case in enumerate(plan['cases']):
        ej, ec = case['ej_ghz'], case['ec_ghz']
        q = -ej/(2*ec)
        # phase/2 has period pi at ng=0: even-order Mathieu a/b families.
        roots = sorted([float(mathieu_a(0,q))] + [float(f(n,q))
                       for n in range(2, 2*plan['levels']+2, 2) for f in (mathieu_a,mathieu_b)])[:plan['levels']]
        reference = [(v-roots[0])*ec*1e9 for v in roots]
        rows=[]
        for ncut in plan['cutoffs']:
            inputs={'ic_a':4*math.pi*e*ej*1e9, 'capacitance_f':e**2/(2*h*ec*1e9),
                    'ng':plan['ng'], 'ncut':ncut, 'n_evals':plan['levels']}
            run = execute_scqubits(prepare_scqubits_input(inputs, out/f'case-{i}-{ncut}'))
            if run.status != 'executed':
                raise ValueError(run.reason)
            payload=json.loads(Path(run.artifacts['result']).read_text())
            si=payload['solver_inputs']
            model=scqubits.Transmon(EJ=si['EJ_GHz'], EC=si['EC_GHz'], ng=si['ng'], ncut=ncut)
            energies, vectors=model.eigensys(evals_count=plan['levels'])
            matrix=model.hamiltonian()
            residual=max(float(np.linalg.norm(matrix@v-energy*v)/(np.linalg.norm(matrix)*np.linalg.norm(v)))
                         for energy,v in zip(energies,vectors.T))
            levels=[v*1e9 for v in payload['quantities']['energy_levels_ghz']]
            vector_levels=(energies-energies[0])*1e9
            # Different LAPACK entrypoints must agree within the declared Hz resolution.
            if max(abs(a-b) for a,b in zip(levels,vector_levels)) > plan['max_reference_hz']:
                raise ValueError('Eigenvalues/eigenvectors disagree')
            rows.append({'ncut':ncut,'levels_hz':levels,'scaled_residual':residual,
                         'eigenvalues_ghz':energies.tolist(),'eigenvectors':vectors.tolist()})
        metrics, passed=assess(rows,reference,plan)
        result['cases'].append({'inputs':case,'rows':rows,'mathieu_roots':roots,
                                'reference_hz':reference,'metrics':metrics,'passed':passed})
    result['passed']=all(c['passed'] for c in result['cases'])
    return result



def canonical_quantities(report, plan, out):
    """Emit executed/rejected evidence; a model benchmark is not physical signoff."""
    from textlayout.evidence.contract import EvidenceStatus, QuantityEvidence

    quantities = []
    for i, case in enumerate(report['cases']):
        _, passed = assess(case['rows'], case['reference_hz'], plan)
        levels = case['rows'][-1]['levels_hz']
        packet = out / f"case-{i}-{plan['cutoffs'][-1]}"
        status = EvidenceStatus.SIMULATION_EXECUTED if passed else EvidenceStatus.CONVERGENCE_FAILED
        for name, value in [('frequency', levels[1]), ('anharmonicity', levels[2]-2*levels[1])]:
            item = QuantityEvidence(
                quantity=f"case_{i}_{name}", status=status,
                extracted_value=value if passed else None,
                extracted_unit='Hz' if passed else None,
                solver=f"scqubits {plan['version']} ideal transmon",
                command=json.dumps([sys.executable, *sys.argv]),
                input_files=[str(packet / 'scqubits_input.json')],
                output_files=[str(packet / 'scqubits_result.json')],
                parser='scripts.check_scqubits_transmon.canonical_quantities',
                notes=['Fixed ideal ng=0 benchmark; numerical metrics in benchmark.json',
                       'No EM, measurement or broader parameter-domain validation',
                       'Canonical default percent tolerance is unused; fixed Hz/residual gates govern this benchmark'],
            )
            quantities.append(item.model_dump(mode='json'))
    return quantities


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    raw=PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PLAN_SHA256:
        raise ValueError('Acceptance plan changed')
    args.out.mkdir(parents=True,exist_ok=False)
    result=execute(json.loads(raw),args.out)
    (args.out/'benchmark.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    canonical = canonical_quantities(result, json.loads(raw), args.out)
    (args.out/'canonical.json').write_text(json.dumps(canonical,indent=2)+'\n')
    manifest={str(p.relative_to(args.out)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(args.out.rglob('*')) if p.is_file()}
    (args.out/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'cases':[c['metrics'] for c in result['cases']]}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
