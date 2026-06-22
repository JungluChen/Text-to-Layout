"""Topology Search — evolutionary and symbolic circuit discovery.

Implements:
    - Genetic superconducting circuit design
    - Symbolic circuit discovery
    - Novelty scoring
    - Patent similarity search (text-based)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Circuit component vocabulary
# ---------------------------------------------------------------------------

COMPONENT_TYPES = [
    "JJ", "CAPACITOR", "INDUCTOR", "CPW", "RESONATOR",
    "SQUID", "IDC", "VIA", "RESISTOR", "PORT",
]

TOPOLOGY_TEMPLATES = {
    "lumped_jpa": ["JJ", "CAPACITOR", "INDUCTOR", "PORT", "PORT"],
    "distributed_jpa": ["JJ", "CPW", "CAPACITOR", "PORT", "PORT"],
    "transmon": ["JJ", "CAPACITOR", "PORT"],
    "fluxonium": ["JJ", "INDUCTOR", "CAPACITOR", "PORT"],
    "cpw_resonator": ["CPW", "PORT", "PORT"],
    "twpa_unit": ["JJ", "JJ", "CAPACITOR", "CPW", "PORT", "PORT"],
    "squid_amplifier": ["SQUID", "CAPACITOR", "INDUCTOR", "PORT", "PORT"],
    "kihc_qubit": ["JJ", "INDUCTOR", "CAPACITOR", "PORT"],
}


@dataclass
class CircuitGenome:
    """Genetic representation of a quantum circuit."""
    components: list[str] = field(default_factory=list)
    connections: list[tuple[int, int]] = field(default_factory=list)
    parameters: dict[str, float] = field(default_factory=dict)
    fitness: float = 0.0
    novelty: float = 0.0
    generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "components": self.components,
            "connections": [[a, b] for a, b in self.connections],
            "parameters": self.parameters,
            "fitness": self.fitness,
            "novelty": self.novelty,
            "generation": self.generation,
        }

    def complexity(self) -> int:
        return len(self.components) + len(self.connections)

    def component_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.components:
            counts[c] = counts.get(c, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Genetic circuit optimizer
# ---------------------------------------------------------------------------

class GeneticCircuitSearch:
    """Evolutionary search for novel quantum circuit topologies.

    Usage::

        search = GeneticCircuitSearch(population_size=50)
        best = search.evolve(
            fitness_fn=my_fitness,
            generations=100,
        )
    """

    def __init__(
        self,
        population_size: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        tournament_size: int = 3,
        seed: int = 42,
    ):
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.rng = random.Random(seed)
        self.population: list[CircuitGenome] = []
        self.generation = 0
        self.history: list[dict[str, Any]] = []

    def initialize(self, templates: list[str] | None = None) -> None:
        """Initialize population from templates or random."""
        self.population = []
        templates = templates or list(TOPOLOGY_TEMPLATES.keys())

        for _ in range(self.pop_size):
            template = self.rng.choice(templates)
            genome = self._from_template(template)
            self.population.append(genome)

    def evolve(
        self,
        fitness_fn: callable,
        generations: int = 50,
        target_fitness: float | None = None,
    ) -> CircuitGenome:
        """Run evolutionary search."""
        if not self.population:
            self.initialize()

        for gen in range(generations):
            self.generation = gen

            # Evaluate fitness
            for genome in self.population:
                genome.fitness = fitness_fn(genome)
                genome.generation = gen

            # Sort by fitness
            self.population.sort(key=lambda g: g.fitness, reverse=True)

            # Record stats
            best = self.population[0]
            avg_fitness = sum(g.fitness for g in self.population) / len(self.population)
            self.history.append({
                "generation": gen,
                "best_fitness": best.fitness,
                "avg_fitness": round(avg_fitness, 4),
                "best_complexity": best.complexity(),
                "best_components": best.component_counts(),
            })

            if target_fitness and best.fitness >= target_fitness:
                break

            # Selection + reproduction
            new_pop = [self.population[0]]  # elitism
            while len(new_pop) < self.pop_size:
                parent1 = self._tournament_select()
                parent2 = self._tournament_select()
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                new_pop.append(child)

            self.population = new_pop

        self.population.sort(key=lambda g: g.fitness, reverse=True)
        return self.population[0]

    def _from_template(self, template_name: str) -> CircuitGenome:
        components = list(TOPOLOGY_TEMPLATES.get(template_name, TOPOLOGY_TEMPLATES["lumped_jpa"]))
        connections = []
        for i in range(len(components) - 1):
            connections.append((i, i + 1))

        params = {}
        for i, c in enumerate(components):
            if c == "JJ":
                params[f"jj_{i}_area"] = self.rng.uniform(0.01, 0.2)
            elif c == "CAPACITOR":
                params[f"cap_{i}_ff"] = self.rng.uniform(10, 500)
            elif c == "CPW":
                params[f"cpw_{i}_width"] = self.rng.uniform(5, 20)
                params[f"cpw_{i}_gap"] = self.rng.uniform(3, 10)

        return CircuitGenome(
            components=components,
            connections=connections,
            parameters=params,
        )

    def _tournament_select(self) -> CircuitGenome:
        tournament = self.rng.sample(self.population, self.tournament_size)
        return max(tournament, key=lambda g: g.fitness)

    def _crossover(self, p1: CircuitGenome, p2: CircuitGenome) -> CircuitGenome:
        if self.rng.random() > self.crossover_rate:
            return CircuitGenome(
                components=list(p1.components),
                connections=list(p1.connections),
                parameters=dict(p1.parameters),
            )

        # Single-point crossover on components
        cut = self.rng.randint(1, min(len(p1.components), len(p2.components)) - 1)
        comps = p1.components[:cut] + p2.components[cut:]
        conns = [(i, i + 1) for i in range(len(comps) - 1)]
        params = {**p1.parameters, **p2.parameters}

        return CircuitGenome(components=comps, connections=conns, parameters=params)

    def _mutate(self, genome: CircuitGenome) -> CircuitGenome:
        if self.rng.random() > self.mutation_rate:
            return genome

        mutation_type = self.rng.choice(["add", "remove", "replace", "param"])

        if mutation_type == "add" and len(genome.components) < 12:
            idx = self.rng.randint(0, len(genome.components))
            new_comp = self.rng.choice(COMPONENT_TYPES)
            genome.components.insert(idx, new_comp)
            genome.connections = [(i, i + 1) for i in range(len(genome.components) - 1)]

        elif mutation_type == "remove" and len(genome.components) > 2:
            idx = self.rng.randint(0, len(genome.components) - 1)
            genome.components.pop(idx)
            genome.connections = [(i, i + 1) for i in range(len(genome.components) - 1)]

        elif mutation_type == "replace":
            idx = self.rng.randint(0, len(genome.components) - 1)
            genome.components[idx] = self.rng.choice(COMPONENT_TYPES)

        elif mutation_type == "param":
            if genome.parameters:
                key = self.rng.choice(list(genome.parameters.keys()))
                genome.parameters[key] *= self.rng.uniform(0.8, 1.2)

        return genome


# ---------------------------------------------------------------------------
# Novelty scoring
# ---------------------------------------------------------------------------

class NoveltyScorer:
    """Score novelty of a circuit design against known designs."""

    def __init__(self):
        self.known_designs: list[dict[str, Any]] = []

    def add_known(self, components: list[str], parameters: dict[str, float]) -> None:
        self.known_designs.append({"components": components, "parameters": parameters})

    def novelty_score(self, genome: CircuitGenome) -> float:
        """Score 0-1, where 1 is maximally novel."""
        if not self.known_designs:
            return 1.0

        min_distance = float("inf")
        genome_features = self._extract_features(genome)

        for known in self.known_designs:
            known_features = self._extract_features_dict(known)
            dist = sum((a - b) ** 2 for a, b in zip(genome_features, known_features))
            min_distance = min(min_distance, math.sqrt(dist))

        # Normalise to 0-1
        return min(1.0, min_distance / 10.0)

    def _extract_features(self, genome: CircuitGenome) -> list[float]:
        counts = genome.component_counts()
        return [float(counts.get(t, 0)) for t in COMPONENT_TYPES] + [
            float(genome.complexity()),
        ]

    def _extract_features_dict(self, design: dict[str, Any]) -> list[float]:
        counts: dict[str, int] = {}
        for c in design.get("components", []):
            counts[c] = counts.get(c, 0) + 1
        return [float(counts.get(t, 0)) for t in COMPONENT_TYPES] + [
            float(len(design.get("components", []))),
        ]


# ---------------------------------------------------------------------------
# Patent similarity (text-based)
# ---------------------------------------------------------------------------

def patent_similarity(text_a: str, text_b: str) -> float:
    """Simple Jaccard similarity between two patent abstracts."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
