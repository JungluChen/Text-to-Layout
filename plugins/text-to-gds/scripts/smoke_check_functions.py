"""Comprehensive smoke check for all major text-to-gds pipeline functions."""
import json
import pathlib
import sys
import tempfile
import traceback

RESULTS = {}


def check(name, fn):
    try:
        ok, detail = fn()
        RESULTS[name] = {"ok": ok, "detail": detail}
    except Exception as e:
        RESULTS[name] = {"ok": False, "detail": f"EXCEPTION: {e}"}
        traceback.print_exc()


# ── imports ──────────────────────────────────────────────────────────────────
from text_to_gds.server import (  # noqa: E402
    list_em_solvers, list_professional_backends, list_pcells,
    list_process_design_kits, list_simulators, list_fabrication_processes,
    check_design_feasibility, compile_layout, run_drc, extract_layout,
    extract_physics_graph_artifact, export_openems_project,
    export_palace_project, export_elmer_project, export_fastcap,
    export_fasthenry, export_hamiltonian_model,
    generate_josephsoncircuits_model_from_physics_graph,
    generate_solver_inputs_from_physics_graph,
    run_analytical_verification, cross_validate_solvers,
    run_simulation, evaluate_signoff_level, review_layout,
    run_process_drc,
)
import text_to_gds.server as srv  # noqa: E402

# ── tmp workspace ─────────────────────────────────────────────────────────────
TMP = pathlib.Path(tempfile.mkdtemp())
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
_orig_root = srv.ARTIFACT_ROOT
srv.ARTIFACT_ROOT = TMP

print(f"\nWorkspace: {TMP}\n")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 — Catalog / list
# ─────────────────────────────────────────────────────────────────────────────
def _list_em_solvers():
    r = list_em_solvers()
    n = len(r.get("solvers", []))
    return n >= 3, f"{n} solvers"

def _list_professional_backends():
    r = list_professional_backends()
    n = len(r) if isinstance(r, list) else 0
    return n >= 4, f"{n} backends"

def _list_pcells():
    r = list_pcells()
    n = len(r.get("pcells", []))
    return n >= 10, f"{n} pcells"

def _list_pdks():
    r = list_process_design_kits()
    return isinstance(r, (dict, list)), type(r).__name__

def _list_simulators():
    r = list_simulators()
    return isinstance(r, (dict, list)), type(r).__name__

def _list_fab_processes():
    r = list_fabrication_processes()
    return isinstance(r, (dict, list)), type(r).__name__

def _check_design_feasibility():
    r = check_design_feasibility("jpa", json.dumps({"center_frequency_ghz": 6.0, "target_gain_db": 20.0}))
    return isinstance(r, dict), list(r.keys())[:4]

check("list_em_solvers", _list_em_solvers)
check("list_professional_backends", _list_professional_backends)
check("list_pcells", _list_pcells)
check("list_pdks", _list_pdks)
check("list_simulators", _list_simulators)
check("list_fab_processes", _list_fab_processes)
check("check_design_feasibility", _check_design_feasibility)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 — Compile + DRC + Extract
# ─────────────────────────────────────────────────────────────────────────────
# Compile once; downstream checks reuse the result
_gds_result = None
_sidecar_path = None

def _compile_layout():
    global _gds_result, _sidecar_path
    r = compile_layout("manhattan_josephson_junction",
                       {"junction_width": 0.3, "junction_height": 0.3},
                       output_name="jj_smoke.gds")
    _gds_result = r
    _sidecar_path = r.get("sidecar_path")
    ok = "gds_path" in r and pathlib.Path(r["gds_path"]).exists()
    return ok, r.get("gds_path", f"no path — keys: {list(r.keys())}")

def _run_drc():
    if not _gds_result or "gds_path" not in _gds_result:
        return False, "compile_layout not run"
    r = run_drc(_gds_result["gds_path"], _gds_result["sidecar_path"])
    return "status" in r, r.get("status", "no status key")

def _extract_layout():
    if not _sidecar_path:
        return False, "no sidecar"
    r = extract_layout(_sidecar_path)
    keys = list(r.keys())[:5] if isinstance(r, dict) else []
    return isinstance(r, dict) and len(r) > 0, keys

def _extract_physics_graph():
    if not _sidecar_path:
        return False, "no sidecar"
    r = extract_physics_graph_artifact(_sidecar_path)
    return "schema" in r or isinstance(r, dict), r.get("schema", "no schema key")

check("compile_layout", _compile_layout)
check("run_drc", _run_drc)
check("extract_layout", _extract_layout)
check("extract_physics_graph_artifact", _extract_physics_graph)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 — Solver input export
# ─────────────────────────────────────────────────────────────────────────────
_cpw_sidecar = None
_cpw_gds = None

def _compile_cpw():
    global _cpw_sidecar, _cpw_gds
    r = compile_layout("cpw_straight", {"length": 500.0, "trace_width": 10.0, "gap": 6.0},
                       output_name="cpw_smoke.gds")
    _cpw_sidecar = r.get("sidecar_path")
    _cpw_gds = r.get("gds_path")
    return "gds_path" in r, r.get("gds_path", f"no path — keys: {list(r.keys())}")

def _export_openems():
    if not _cpw_sidecar:
        return False, "no cpw sidecar"
    r = export_openems_project(_cpw_sidecar)
    ok = isinstance(r, dict)
    return ok, r.get("status", list(r.keys())[:3] if isinstance(r, dict) else "not dict")

def _export_palace():
    if not _cpw_gds:
        return False, "no cpw gds"
    r = export_palace_project(_cpw_gds, sidecar_path=_cpw_sidecar)
    return isinstance(r, dict), list(r.keys())[:3] if isinstance(r, dict) else "not dict"

def _export_elmer():
    if not _cpw_gds:
        return False, "no cpw gds"
    r = export_elmer_project(_cpw_gds, sidecar_path=_cpw_sidecar)
    return isinstance(r, dict), list(r.keys())[:3] if isinstance(r, dict) else "not dict"

def _export_fastcap():
    if not _cpw_gds:
        return False, "no cpw gds"
    r = export_fastcap(_cpw_gds, sidecar_path=_cpw_sidecar)
    return isinstance(r, dict), list(r.keys())[:3] if isinstance(r, dict) else "not dict"

def _export_fasthenry():
    if not _cpw_gds:
        return False, "no cpw gds"
    r = export_fasthenry(_cpw_gds, sidecar_path=_cpw_sidecar)
    return isinstance(r, dict), list(r.keys())[:3] if isinstance(r, dict) else "not dict"

def _generate_solver_inputs():
    if not _cpw_sidecar:
        return False, "no cpw sidecar"
    # use the physics graph from extract step
    pg = extract_physics_graph_artifact(_cpw_sidecar)
    pg_file = TMP / "cpw_test.physics_graph.json"
    pg_file.write_text(json.dumps(pg))
    r = generate_solver_inputs_from_physics_graph(str(pg_file))
    return isinstance(r, dict), list(r.keys())[:4] if isinstance(r, dict) else "not dict"

check("compile_cpw", _compile_cpw)
check("export_openems_project", _export_openems)
check("export_palace_project", _export_palace)
check("export_elmer_project", _export_elmer)
check("export_fastcap", _export_fastcap)
check("export_fasthenry", _export_fasthenry)
check("generate_solver_inputs", _generate_solver_inputs)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4 — Hamiltonian / JC model export
# ─────────────────────────────────────────────────────────────────────────────
_jpa_sidecar = None

_jpa_gds = None

def _compile_jpa():
    global _jpa_sidecar, _jpa_gds
    r = compile_layout("lumped_element_jpa_seed",
                       {"center_frequency_ghz": 6.0, "target_gain_db": 20.0},
                       output_name="jpa_smoke.gds")
    _jpa_sidecar = r.get("sidecar_path")
    _jpa_gds = r.get("gds_path")
    return "gds_path" in r, r.get("gds_path", f"no path — keys: {list(r.keys())}")

def _export_hamiltonian():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    r = export_hamiltonian_model(_jpa_sidecar)
    return isinstance(r, dict), list(r.keys())[:4] if isinstance(r, dict) else "not dict"

def _gen_jc_model():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    pg = extract_physics_graph_artifact(_jpa_sidecar)
    pg_file = TMP / "jpa_test.physics_graph.json"
    pg_file.write_text(json.dumps(pg))
    r = generate_josephsoncircuits_model_from_physics_graph(str(pg_file))
    return isinstance(r, dict), list(r.keys())[:4] if isinstance(r, dict) else "not dict"

check("compile_jpa", _compile_jpa)
check("export_hamiltonian_model", _export_hamiltonian)
check("generate_jc_model", _gen_jc_model)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5 — Simulation
# ─────────────────────────────────────────────────────────────────────────────
def _run_simulation_scqubits():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    r = run_simulation(_jpa_sidecar, simulator="scqubits")
    ok = isinstance(r, dict) and "schema" in r
    return ok, r.get("engine", list(r.keys())[:3])

def _run_simulation_josephsoncircuits():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    r = run_simulation(_jpa_sidecar, simulator="josephsoncircuits")
    ok = isinstance(r, dict) and "schema" in r
    return ok, r.get("engine", list(r.keys())[:3])

check("run_simulation_scqubits", _run_simulation_scqubits)
check("run_simulation_josephsoncircuits", _run_simulation_josephsoncircuits)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 6 — Analytical verification + cross-validate
# ─────────────────────────────────────────────────────────────────────────────
def _run_analytical_verification():
    r = run_analytical_verification(
        output_name="smoke-check-theory",
        center_frequency_ghz=6.0,
        kappa_mhz=120.0,
        pump_coupling_mhz=55.0,
    )
    return isinstance(r, dict), list(r.keys())[:4] if isinstance(r, dict) else "not dict"

def _cross_validate():
    # cross_validate_solvers takes a list of source dicts, not a sidecar path
    sources = [
        {"z0_ohm": 50.1, "method": "conformal_mapping", "solver": "analytical"},
        {"z0_ohm": 49.8, "method": "conformal_mapping", "solver": "extracted"},
    ]
    r = cross_validate_solvers(sources, quantity="z0_ohm", tolerance_pct=5.0)
    return isinstance(r, dict), list(r.keys())[:4] if isinstance(r, dict) else "not dict"

check("run_analytical_verification", _run_analytical_verification)
check("cross_validate_solvers", _cross_validate)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 7 — Review & signoff
# ─────────────────────────────────────────────────────────────────────────────
def _review_layout():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    r = review_layout(_jpa_sidecar)
    return isinstance(r, dict), r.get("score", r.get("approved", "no score"))

def _evaluate_signoff():
    if not _jpa_sidecar:
        return False, "no jpa sidecar"
    ext = extract_layout(_jpa_sidecar)
    pg = extract_physics_graph_artifact(_jpa_sidecar)
    evidence = {"extraction": ext, "physics_graph": pg, "sidecar_path": _jpa_sidecar}
    r = evaluate_signoff_level(json.dumps(evidence))
    return isinstance(r, dict), r.get("level", "no level")

check("review_layout", _review_layout)
check("evaluate_signoff_level", _evaluate_signoff)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 8 — Process DRC
# ─────────────────────────────────────────────────────────────────────────────
def _run_process_drc():
    if not _gds_result or "gds_path" not in _gds_result:
        return False, "no gds"
    deck = str(PROJECT_ROOT / "drc" / "superconducting_min_width.drc")
    r = run_process_drc(_gds_result["gds_path"], deck_path=deck)
    return isinstance(r, dict), r.get("status", list(r.keys())[:3])

check("run_process_drc", _run_process_drc)


# ─────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────────────
srv.ARTIFACT_ROOT = _orig_root

print("\n" + "=" * 60)
print("FUNCTION SMOKE CHECK RESULTS")
print("=" * 60)

groups = {
    "Group 1: Catalog / List": [
        "list_em_solvers", "list_professional_backends", "list_pcells",
        "list_pdks", "list_simulators", "list_fab_processes",
        "check_design_feasibility"
    ],
    "Group 2: Compile + DRC + Extract": [
        "compile_layout", "run_drc", "extract_layout",
        "extract_physics_graph_artifact"
    ],
    "Group 3: Solver Input Export": [
        "compile_cpw", "export_openems_project", "export_palace_project",
        "export_elmer_project", "export_fastcap", "export_fasthenry",
        "generate_solver_inputs"
    ],
    "Group 4: Hamiltonian / JC Model": [
        "compile_jpa", "export_hamiltonian_model", "generate_jc_model"
    ],
    "Group 5: Simulation": [
        "run_simulation_scqubits", "run_simulation_josephsoncircuits"
    ],
    "Group 6: Analytical + Cross-Validate": [
        "run_analytical_verification", "cross_validate_solvers"
    ],
    "Group 7: Review & Signoff": [
        "review_layout", "evaluate_signoff_level"
    ],
    "Group 8: Process DRC": [
        "run_process_drc"
    ],
}

all_pass = True
for grp, keys in groups.items():
    grp_ok = all(RESULTS.get(k, {}).get("ok", False) for k in keys)
    marker = "OK" if grp_ok else "FAIL"
    print(f"\n  [{marker}] {grp}")
    for k in keys:
        res = RESULTS.get(k, {"ok": False, "detail": "not run"})
        icon = "+" if res["ok"] else "X"
        print(f"    [{icon}] {k:<42}  {res['detail']}")
    if not grp_ok:
        all_pass = False

print("\n" + "=" * 60)
print("OVERALL:", "ALL PASS" if all_pass else "SOME FAILURES — see above")
print("=" * 60)
sys.exit(0 if all_pass else 1)
