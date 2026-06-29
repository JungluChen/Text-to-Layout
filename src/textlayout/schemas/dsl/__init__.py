"""Layout DSL schemas."""

from __future__ import annotations

from textlayout.schemas.dsl.base import DSL_VERSION, LayoutSpec
from textlayout.schemas.dsl.cpw import CPWSpec
from textlayout.schemas.dsl.idc import IDCSpec

__all__ = ["DSL_VERSION", "CPWSpec", "IDCSpec", "LayoutSpec"]
