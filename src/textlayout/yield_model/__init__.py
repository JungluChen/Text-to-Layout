"""JJ/SQUID critical-current variability and fabrication-yield modeling.

Why this exists: drawing one SQUID loop at a target Jc proves geometry, not
manufacturability. Real wafers have Jc spread (wafer-to-wafer and
junction-to-junction), which maps directly into qubit-frequency spread. This
package makes that spread explicit via seeded Monte Carlo propagation from
process statistics through exact JJ/SQUID physics to a frequency distribution
and yield percentage — see :mod:`textlayout.yield_model.physics` for the exact
relations and :mod:`textlayout.yield_model.monte_carlo` for the sampling model.

All process defaults are illustrative (``calibration="illustrative"``) until
replaced by process-measured statistics via the measurement-calibration loop.
"""

from textlayout.yield_model.models import (
    YIELD_SCHEMA,
    FrequencyTarget,
    JJProcessModel,
    JunctionGeometry,
    SquidGeometry,
    WorstCaseCorner,
    YieldResult,
    YieldStatistics,
)
from textlayout.yield_model.monte_carlo import run_jj_yield, run_qubit_array_yield
from textlayout.yield_model.physics import (
    H_JS,
    PHI0_WB,
    ec_ghz,
    ej_ghz,
    ej_over_ec,
    ic_ua,
    lc_resonance_ghz,
    lj_nh,
    squid_ic_eff_ua,
    squid_lj_nh,
    transmon_f01_ghz,
)
from textlayout.yield_model.report import render_markdown, write_yield_report

__all__ = [
    "H_JS",
    "PHI0_WB",
    "YIELD_SCHEMA",
    "FrequencyTarget",
    "JJProcessModel",
    "JunctionGeometry",
    "SquidGeometry",
    "WorstCaseCorner",
    "YieldResult",
    "YieldStatistics",
    "ec_ghz",
    "ej_ghz",
    "ej_over_ec",
    "ic_ua",
    "lc_resonance_ghz",
    "lj_nh",
    "render_markdown",
    "run_jj_yield",
    "run_qubit_array_yield",
    "squid_ic_eff_ua",
    "squid_lj_nh",
    "transmon_f01_ghz",
    "write_yield_report",
]
