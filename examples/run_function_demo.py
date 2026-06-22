"""List or execute any public function defined by text_to_gds.server."""

from __future__ import annotations

import argparse
import inspect
import json
from typing import Any

from text_to_gds import server


def public_functions() -> dict[str, Any]:
    return {
        name: function
        for name, function in inspect.getmembers(server, inspect.isfunction)
        if not name.startswith("_") and function.__module__ == server.__name__ and name != "main"
    }


def main() -> None:
    functions = public_functions()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("function", help="Function name, or 'list'")
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON keyword arguments")
    args = parser.parse_args()
    if args.function == "list":
        for name, function in functions.items():
            summary = (inspect.getdoc(function) or "").splitlines()[0]
            print(f"{name}{inspect.signature(function)}\n  {summary}")
        return
    if args.function not in functions:
        raise SystemExit(f"Unknown public function {args.function!r}. Run with 'list'.")
    kwargs = json.loads(args.arguments)
    if not isinstance(kwargs, dict):
        raise SystemExit("arguments must decode to a JSON object")
    result = functions[args.function](**kwargs)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
