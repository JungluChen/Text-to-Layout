"""The textlayout / text_to_gds namespace boundary is enforced, not just documented.

`textlayout` is the supported implementation namespace; `text_to_gds` is the
frozen legacy MCP surface. These tests run the same checks as
``scripts/check_namespace_boundary.py`` inside the local suite (so a violation
fails ``pytest``, not only CI), and prove the deprecation-shim mechanism that
lets legacy modules be retired into thin re-exports of ``textlayout``.
"""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _guard():
    spec = importlib.util.spec_from_file_location(
        "check_namespace_boundary", SCRIPTS_DIR / "check_namespace_boundary.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = _guard()


class TestInwardBoundary:
    def test_textlayout_never_imports_legacy(self):
        """The product path must not depend on the frozen legacy package."""
        violations = GUARD.boundary_violations()
        assert violations == [], (
            "textlayout imports text_to_gds — the product must not depend on legacy:\n"
            + "\n".join(f"  {f}: {stmt}" for f, stmt in violations)
        )


class TestLegacyFreeze:
    def test_no_new_legacy_implementation_files(self):
        """text_to_gds may only grow shims; new implementation belongs in textlayout."""
        violations = GUARD.freeze_violations()
        assert violations == [], (
            "new non-shim implementation added to frozen text_to_gds:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_manifest_matches_repo(self):
        """The implementation freeze manifest is deliberately empty."""
        manifest = GUARD.MANIFEST.read_text(encoding="utf-8").splitlines()
        pinned = [ln.strip() for ln in manifest if ln.strip() and not ln.startswith("#")]
        assert pinned == []


class TestShimClassifier:
    """`is_shim_source` decides freeze exemption; it must be precise both ways."""

    def test_marker_assignment_is_a_shim(self):
        assert GUARD.is_shim_source("__textlayout_shim__ = True\n") is True

    def test_helper_call_is_a_shim(self):
        src = (
            "from text_to_gds._deprecation import deprecated_reexport\n"
            "__all__ = deprecated_reexport(globals(), 'textlayout', since='0.3.0')\n"
        )
        assert GUARD.is_shim_source(src) is True

    def test_plain_implementation_is_not_a_shim(self):
        src = "def compute():\n    return 42\n"
        assert GUARD.is_shim_source(src) is False

    def test_incidental_import_of_textlayout_is_not_a_shim(self):
        # Importing textlayout does not make a legacy *implementation* file a shim.
        src = "import textlayout\n\ndef run():\n    return textlayout.__version__\n"
        assert GUARD.is_shim_source(src) is False

    def test_syntax_error_is_not_a_shim(self):
        assert GUARD.is_shim_source("def (:\n") is False


class TestFreezeRejectsNewImplementation:
    """The guard actually rejects a newly-added implementation file, not vacuously pass."""

    def test_unlisted_non_shim_file_is_flagged(self, tmp_path, monkeypatch):
        legacy = tmp_path / "src" / "text_to_gds"
        legacy.mkdir(parents=True)
        (legacy / "__init__.py").write_text(
            "__textlayout_shim__ = True\n", encoding="utf-8"
        )
        (legacy / "brand_new_feature.py").write_text("X = 1\n", encoding="utf-8")
        (legacy / "retired_module.py").write_text(
            "__textlayout_shim__ = True\n", encoding="utf-8"
        )
        monkeypatch.setattr(GUARD, "ROOT", tmp_path)
        monkeypatch.setattr(GUARD, "LEGACY_SRC", legacy)

        flagged = GUARD.freeze_violations()
        assert flagged == ["src/text_to_gds/brand_new_feature.py"], flagged

    def test_boundary_detects_a_legacy_import(self, tmp_path, monkeypatch):
        tl = tmp_path / "src" / "textlayout"
        tl.mkdir(parents=True)
        (tl / "clean.py").write_text("import numpy\n", encoding="utf-8")
        (tl / "leaky.py").write_text(
            "from text_to_gds.evidence import golden_compare\n", encoding="utf-8"
        )
        monkeypatch.setattr(GUARD, "ROOT", tmp_path)
        monkeypatch.setattr(GUARD, "TEXTLAYOUT_SRC", tl)

        flagged = GUARD.boundary_violations()
        assert ("src/textlayout/leaky.py", "from text_to_gds.evidence import ...") in flagged
        assert all("clean.py" not in f for f, _ in flagged)


class TestDeprecationShimMechanism:
    """`deprecated_reexport` yields a warning-emitting, identity-preserving re-export."""

    def test_compat_module_reexports_textlayout(self):
        import textlayout

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import text_to_gds.textlayout_compat as compat

        # Every re-exported name is the *same object* as textlayout's — a true alias.
        for name in compat.__all__:
            assert getattr(compat, name) is getattr(textlayout, name), name
        assert compat.LayoutSpec is textlayout.LayoutSpec
        assert getattr(compat, GUARD.SHIM_MARKER) is True

    def test_deep_legacy_module_is_identity_preserving_alias(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from text_to_gds.core.units import Quantity as legacy_quantity
        from textlayout._legacy.core.units import Quantity

        assert legacy_quantity is Quantity

    def test_helper_warns_and_marks(self):
        from text_to_gds._deprecation import deprecated_reexport

        ns: dict[str, object] = {"__name__": "text_to_gds.fake_shim"}
        with pytest.warns(DeprecationWarning, match="deprecated compatibility shim"):
            exported = deprecated_reexport(
                ns, "textlayout", names=["LayoutSpec"], since="0.3.0", removal="1.0.0"
            )
        import textlayout

        assert exported == ["LayoutSpec"]
        assert ns["LayoutSpec"] is textlayout.LayoutSpec
        assert ns[GUARD.SHIM_MARKER] is True

    def test_helper_rejects_non_textlayout_target(self):
        from text_to_gds._deprecation import deprecated_reexport

        with pytest.raises(ValueError, match="under textlayout"):
            deprecated_reexport({"__name__": "x"}, "numpy", since="0.3.0")

    def test_helper_rejects_missing_name(self):
        from text_to_gds._deprecation import deprecated_reexport

        with pytest.raises(AttributeError, match="does not export"):
            deprecated_reexport(
                {"__name__": "x"}, "textlayout", names=["NoSuchSymbol"], since="0.3.0"
            )
