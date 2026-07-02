"""Command-line interface for textlayout.

Four subcommands cover the usage modes from a single shared core:

    textlayout prompt "Create a 0.6 pF IDC ..." --out out/idc_demo  # NL -> closed loop
    textlayout generate spec.json --out out_dir   # DSL file -> verified artifacts
    textlayout verify   spec.json                 # DSL file -> verification report
    textlayout serve    --host 0.0.0.0 --port 8000  # run the plugin API server
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from textlayout import __version__, build_default_workflow, build_from_text_workflow
from textlayout.errors import TextLayoutError
from textlayout.schemas.dsl import LayoutSpec


def _load_spec(path: str) -> LayoutSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LayoutSpec.model_validate(data)


def _cmd_prompt(args: argparse.Namespace) -> int:
    workflow = build_from_text_workflow()
    result = workflow.run(
        args.prompt,
        args.out,
        tolerance_percent=args.tolerance,
        execute_solver=not args.no_solver,
        solver_executable=args.executable,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 2


def _cmd_generate(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    spec = _load_spec(args.spec)
    result = workflow.run(spec, output_dir=args.out)
    print(json.dumps({
        "summary": result.summary,
        "verification": result.report.to_dict(),
        "files": dict(result.files),
    }, indent=2))
    return 0 if result.report.passed else 2


def _cmd_verify(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    report = workflow.verify_only(_load_spec(args.spec))
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 2


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "textlayout.backend.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=False,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="textlayout", description="Text-to-Layout CLI")
    parser.add_argument("--version", action="version", version=f"textlayout {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser(
        "prompt",
        help="Natural-language request -> intent, layout, verification, simulation, report.",
    )
    p_prompt.add_argument("prompt", help="e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'")
    p_prompt.add_argument("--out", default="out/textlayout_prompt", help="Output directory.")
    p_prompt.add_argument("--tolerance", type=float, default=5.0, help="Tolerance in percent.")
    p_prompt.add_argument(
        "--no-solver", action="store_true",
        help="Prepare solver inputs but do not attempt to execute a solver.",
    )
    p_prompt.add_argument("--executable", default=None, help="Explicit FasterCap/FastCap path.")
    p_prompt.set_defaults(func=_cmd_prompt)

    p_gen = sub.add_parser("generate", help="Generate verified artifacts from a DSL file.")
    p_gen.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_gen.add_argument("--out", default="workspace/textlayout", help="Output directory.")
    p_gen.set_defaults(func=_cmd_generate)

    p_ver = sub.add_parser("verify", help="Verify a DSL file (no export).")
    p_ver.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_ver.set_defaults(func=_cmd_verify)

    p_srv = sub.add_parser("serve", help="Run the FastAPI plugin server.")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
        return result
    except TextLayoutError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
