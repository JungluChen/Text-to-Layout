"""Validated inventory of user-requested integration candidates.

The source hints are supplied by the mission brief, not verified upstream
identities. Loading the catalog must never import, probe, or execute a tool.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True, slots=True)
class IntegrationTarget:
    id: int
    pillar: int
    name: str
    source_hint: str | None


@lru_cache(maxsize=1)
def load_targets() -> tuple[IntegrationTarget, ...]:
    """Load all 100 candidate slots without asserting source or license validity."""
    source = resources.files("textlayout.integrations").joinpath("targets.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != "textlayout.integration-candidates.v1":
        raise ValueError("integration candidate catalog schema mismatch")
    pillars = payload.get("pillars")
    if not isinstance(pillars, list) or [p.get("id") for p in pillars] != list(
        range(1, 11)
    ):
        raise ValueError("integration candidate pillars must be 1..10")
    raw = payload.get("targets")
    if not isinstance(raw, list):
        raise ValueError("integration candidate target list is missing")
    targets = tuple(IntegrationTarget(**item) for item in raw)
    if [target.id for target in targets] != list(range(1, 101)):
        raise ValueError("integration candidate IDs must be 1..100")
    if any(target.pillar != (target.id - 1) // 10 + 1 for target in targets):
        raise ValueError("integration candidate pillar assignments are inconsistent")
    if len({target.name.casefold() for target in targets}) != 100:
        raise ValueError("integration candidate names must be unique")
    return targets
