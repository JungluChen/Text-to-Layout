from __future__ import annotations

import warnings

import pytest


def test_product_deprecations_are_errors() -> None:
    with pytest.raises(DeprecationWarning, match="product deprecation"):
        warnings.warn_explicit(
            "product deprecation",
            DeprecationWarning,
            filename="product.py",
            lineno=1,
            module="textlayout.product",
        )


def test_confirmed_third_party_deprecation_is_not_promoted_by_product_filter() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        warnings.warn_explicit(
            "third-party deprecation",
            DeprecationWarning,
            filename="dependency.py",
            lineno=1,
            module="third_party_dependency",
        )
    assert len(caught) == 1
