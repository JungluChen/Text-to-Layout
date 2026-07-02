import importlib.util
from pathlib import Path


def test_readme_claims_have_code_tests_and_artifacts() -> None:
    root = Path(__file__).parents[2]
    script = root / "scripts" / "check_readme_claims.py"
    spec = importlib.util.spec_from_file_location("check_readme_claims", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate_claims(root) == []
