from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any

from textlayout._legacy.simulation.solver_adapter import BaseSolverAdapter


class JosephsonCircuitsAdapter(BaseSolverAdapter):
    def __init__(
        self,
        executable: str = "julia",
        *,
        timeout_seconds: int = 600,
    ) -> None:
        super().__init__(solver_name="JosephsonCircuits", executable=executable)
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        tools_root = Path(__file__).resolve().parents[3] / ".tools"
        julia_bin = tools_root / "julia" / "bin" / "julia"
        if julia_bin.exists():
            try:
                result = subprocess.run(
                    [str(julia_bin), "-e", "import Pkg; Pkg.status(\"JosephsonCircuits\")"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return result.returncode == 0 and "JosephsonCircuits" in result.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

        try:
            result = subprocess.run(
                [self.executable, "-e", "import Pkg; Pkg.status(\"JosephsonCircuits\")"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0 and "JosephsonCircuits" in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _resolve_julia(self) -> str:
        tools_root = Path(__file__).resolve().parents[3] / ".tools"
        julia_bin = tools_root / "julia" / "bin" / "julia"
        if julia_bin.exists():
            return str(julia_bin)
        return self.executable

    def _generate_input(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path,
    ) -> Path:
        freq_ghz = float(input_data.get("frequency_ghz", 5.0))
        freq_hz = freq_ghz * 1e9
        L_j = float(input_data.get("josephson_inductance_ph", 100.0)) * 1e-12
        C_j = float(input_data.get("josephson_capacitance_ff", 100.0)) * 1e-15
        n_modes = int(input_data.get("n_modes", 3))
        analysis_type = input_data.get("analysis_type", "reflection")

        if analysis_type == "two_port":
            s_param_indices = [(1, 1), (2, 1)]
        else:
            s_param_indices = [(1, 1)]

        freq_points = [
            f"{freq_hz * (1.0 + 0.01 * i):.6g}"
            for i in range(max(n_modes * 5, 21))
        ]

        freq_str = ", ".join(freq_points)
        s_param_specs = ", ".join(
            f"(({p[0]}, {p[1]}), 0, 0)" for p in s_param_indices
        )

        julia_script = textwrap.dedent(
            "using JosephsonCircuits\n"
            "using JSON\n"
            f"\n"
            f"freq = [{freq_str}]\n"
            "omega = 2pi .* freq\n"
            "\n"
            "cb = circuit()\n"
            f"component!(cb, :Lj, 1, 2, L={L_j:.6e})\n"
            f"component!(cb, :C, 1, 2, C={C_j:.6e})\n"
            f'if "{analysis_type}" == "two_port"\n'
            f"    component!(cb, :Lj, 3, 4, L={L_j:.6e})\n"
            f"    component!(cb, :C, 3, 4, C={C_j:.6e})\n"
            "    component!(cb, :short, 2, 0)\n"
            "    component!(cb, :short, 4, 0)\n"
            "    component!(cb, :open, 1, 0)\n"
            "    component!(cb, :open, 3, 0)\n"
            "else\n"
            "    component!(cb, :short, 2, 0)\n"
            "    component!(cb, :open, 1, 0)\n"
            "end\n"
            "\n"
            "ntwk = network(cb, omega)\n"
            "solve!(ntwk)\n"
            "\n"
            "results = Dict{String,Any}()\n"
            'results["frequencies_hz"] = freq\n'
            "s_data = Dict{String,Any}()\n"
            f"for s in [{s_param_specs}]\n"
            '    key = "S$(s[1])S$(s[2])"\n'
            "    data = get_s(ntwk, s[1], s[2])\n"
            '    s_data[key] = [Dict("re" => real(v), "im" => imag(v)) for v in data]\n'
            "end\n"
            'results["s_parameters"] = s_data\n'
            "\n"
            'open(joinpath(@__DIR__, "josephsoncircuits_results.json"), "w") do f\n'
            "    JSON.print(f, results, 2)\n"
            "end\n"
        )

        script_path = output_dir / "josephsoncircuits_sim.jl"
        script_path.write_text(julia_script, encoding="utf-8")
        return script_path

    def _run_solver(self, input_path: Path) -> None:
        julia_bin = self._resolve_julia()
        result = subprocess.run(
            [julia_bin, str(input_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            cwd=str(input_path.parent),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"JosephsonCircuits.jl exited with code {result.returncode}: "
                f"{result.stderr[-500:]}"
            )

    def _parse_output(self, output_path: Path) -> dict[str, Any]:
        import json

        results_path = output_path.parent / "josephsoncircuits_results.json"
        if not results_path.exists():
            return {"status": "no_results", "parsed_data": None}
        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
            return {
                "status": "parsed",
                "frequencies_hz": data.get("frequencies_hz", []),
                "s_parameters": data.get("s_parameters", {}),
            }
        except (json.JSONDecodeError, KeyError) as exc:
            return {"status": "parse_error", "error": str(exc), "parsed_data": None}

    def _validate_output(self, parsed: dict[str, Any]) -> bool:
        return parsed.get("status") == "parsed" and bool(parsed.get("frequencies_hz"))
