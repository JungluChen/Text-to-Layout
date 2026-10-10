# scqubits — entry 005, acceptance pending

Document class: MANUAL_DOCUMENTATION.

Source: https://github.com/scqubits/scqubits/tree/9c495f7653aa09de18b1856a30f32d40ad5333c5
(tag v4.1, installed distribution 4.1.0). Installed BSD-3-Clause license and
package metadata retained in the 2026-10-09-210224 audit. Transmon source matches
that revision byte-for-byte, SHA256
c3e4825e1b38d8b6399adb0fd980b71179b2c9f10cdbce5ae41135a36681eb50.
Optional runtime only; no added base dependency or vendored source.

The existing typed adapter converts explicit SI current and capacitance to
EJ/h and EC/h in GHz and retains inputs/output lineage. Correction b62eab5
uses exact defining constants for Phi0=h/(2e), preserving legacy agreement.
See the conversion report 2026-10-10-030427. Execution alone leaves
convergence and reference comparison NOT_EVALUATED.

The locked plan references/scqubits/transmon-plan.json defines two new ideal
ng=0 cases: EJ/h,EC/h = (18,0.24) and (24,0.2) GHz. Cutoffs 20/30/40 retain six
excitation levels. Absolute 1 Hz limits on last refinement and final reference
agreement are numerical resolution requirements, not experimental uncertainty.
Scaled eigenpair residual <=1e-12 is a separate algebraic quality check.
All limits and cases were written before the benchmark executed.

Reference: setting x=phase/2 gives Mathieu parameter q=-EJ/(2EC) and
characteristic value E/EC. At ng=0, the phase wavefunction is 2pi-periodic,
so even-order a/b families give the pi-periodic x spectrum. Sort a0,a2,b2,...
and subtract the ground energy. This does not extend to arbitrary ng without
changing boundary conditions. scipy.special Mathieu functions are a different
algorithm from scqubits' tridiagonal charge Hamiltonian, but share SciPy;
do not claim a separate numerical library or measured-device validation.

Run `PYTHONPATH=src uv run --no-sync python scripts/check_scqubits_transmon.py --out NEW_DIR`
from the repository root with scqubits 4.1.0 installed. Keep both repeated
packets; independently inspect hashes, inputs, eigenvectors and reported metrics.
Other offsets, noise, multimode circuits, EM extraction, canonical acceptance
integration and dedicated three-platform execution remain pending. Checklist
005 stays unchecked until the documented scope has all required evidence.
