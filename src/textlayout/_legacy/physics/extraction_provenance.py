from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedQuantity:
    value: float
    unit: str
    source: str
    method: str
    validity_range: tuple[float, float]
    confidence: float
    dependencies: list[str] = field(default_factory=list)
    note: str = ""


class ProvenanceChain:
    def __init__(self) -> None:
        self._store: dict[str, ExtractedQuantity] = {}

    def add(self, name: str, quantity: ExtractedQuantity) -> None:
        self._store[name] = quantity

    def get(self, name: str) -> ExtractedQuantity:
        return self._store[name]

    def resolve(self, name: str) -> list[ExtractedQuantity]:
        visited: set[str] = set()
        result: list[ExtractedQuantity] = []
        self._walk(name, visited, result)
        all_sources = {q.source for q in self._store.values()}
        if "estimated" in all_sources and len(all_sources) > 1:
            raise ValueError(
                f"Cannot mix sources {sorted(all_sources)} in provenance chain for '{name}'"
            )
        return result

    def _walk(
        self,
        name: str,
        visited: set[str],
        result: list[ExtractedQuantity],
    ) -> None:
        if name in visited:
            return
        visited.add(name)
        q = self._store[name]
        result.append(q)
        for dep in q.dependencies:
            self._walk(dep, visited, result)
