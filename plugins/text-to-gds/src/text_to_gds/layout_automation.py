"""Microwave routing, floorplanning, hierarchy, and reusable layout primitives."""

from __future__ import annotations

import heapq
import math
from typing import Any

from text_to_gds.physics_extensions import optimize_cpw_impedance


def route_microwave(
    start_um: tuple[float, float],
    end_um: tuple[float, float],
    *,
    obstacles: list[list[float]] | None = None,
    grid_um: float = 10.0,
    clearance_um: float = 10.0,
) -> dict[str, Any]:
    """A* Manhattan router with rectangular keep-out expansion."""
    if grid_um <= 0.0 or clearance_um < 0.0:
        raise ValueError("Grid must be positive and clearance non-negative")
    start = tuple(round(value / grid_um) for value in start_um)
    goal = tuple(round(value / grid_um) for value in end_um)
    blocked = set()
    for box in obstacles or []:
        xmin, ymin, xmax, ymax = box
        for x in range(math.floor((xmin - clearance_um) / grid_um), math.ceil((xmax + clearance_um) / grid_um) + 1):
            for y in range(math.floor((ymin - clearance_um) / grid_um), math.ceil((ymax + clearance_um) / grid_um) + 1):
                blocked.add((x, y))
    blocked.discard(start)
    blocked.discard(goal)
    queue = [(0.0, start)]
    cost = {start: 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    limit = 200000
    while queue and limit > 0:
        limit -= 1
        _, current = heapq.heappop(queue)
        if current == goal:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = current[0] + dx, current[1] + dy
            if neighbor in blocked:
                continue
            new_cost = cost[current] + 1.0
            if new_cost < cost.get(neighbor, math.inf):
                cost[neighbor] = new_cost
                previous[neighbor] = current
                heuristic = abs(neighbor[0] - goal[0]) + abs(neighbor[1] - goal[1])
                heapq.heappush(queue, (new_cost + heuristic, neighbor))
    if goal not in cost:
        raise ValueError("No route found within search limit")
    points = [goal]
    while points[-1] != start:
        points.append(previous[points[-1]])
    points.reverse()
    compressed = [points[0]]
    for index in range(1, len(points) - 1):
        before, current, after = points[index - 1], points[index], points[index + 1]
        if (current[0] - before[0], current[1] - before[1]) != (after[0] - current[0], after[1] - current[1]):
            compressed.append(current)
    compressed.append(points[-1])
    route = [[x * grid_um, y * grid_um] for x, y in compressed]
    return {"schema": "text-to-gds.microwave-route.v1", "points_um": route, "length_um": (len(points) - 1) * grid_um, "bend_count": max(len(route) - 2, 0)}


def route_cpw(
    start_um: tuple[float, float],
    end_um: tuple[float, float],
    *,
    target_impedance_ohm: float = 50.0,
    epsilon_r: float = 11.45,
    min_width_um: float = 0.2,
    **routing: Any,
) -> dict[str, Any]:
    route = route_microwave(start_um, end_um, **routing)
    route["cross_section"] = optimize_cpw_impedance(target_ohm=target_impedance_ohm, epsilon_r=epsilon_r, min_width_um=min_width_um)
    return route


def optimize_ground_plane(
    *, chip_bbox_um: list[float], keepouts_um: list[list[float]], hole_pitch_um: float = 50.0, hole_size_um: float = 5.0
) -> dict[str, Any]:
    if hole_pitch_um <= hole_size_um or hole_size_um <= 0.0:
        raise ValueError("Hole pitch must exceed positive hole size")
    xmin, ymin, xmax, ymax = chip_bbox_um
    holes = []
    x = xmin + hole_pitch_um
    while x < xmax - hole_pitch_um:
        y = ymin + hole_pitch_um
        while y < ymax - hole_pitch_um:
            if not any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for box in keepouts_um):
                holes.append([x, y, hole_size_um])
            y += hole_pitch_um
        x += hole_pitch_um
    return {"ground_bbox_um": chip_bbox_um, "keepouts_um": keepouts_um, "flux_holes": holes, "open_area_fraction": len(holes) * hole_size_um**2 / max((xmax - xmin) * (ymax - ymin), 1e-30)}


def airbridge_generator(*, span_um: float, width_um: float = 3.0, landing_um: float = 8.0, clearance_um: float = 2.0) -> dict[str, Any]:
    if min(span_um, width_um, landing_um, clearance_um) <= 0.0:
        raise ValueError("Airbridge dimensions must be positive")
    return {"cell": "airbridge", "parameters": {"span_um": span_um, "width_um": width_um, "landing_um": landing_um, "clearance_um": clearance_um}, "layers": {"landing": [5, 0], "bridge": [20, 0], "release": [21, 0]}}


def crossover_generator(*, lower_width_um: float, upper_width_um: float, dielectric_thickness_nm: float, overlap_um: float) -> dict[str, Any]:
    if min(lower_width_um, upper_width_um, dielectric_thickness_nm, overlap_um) <= 0.0:
        raise ValueError("Crossover dimensions must be positive")
    return {"cell": "crossover", "parameters": {"lower_width_um": lower_width_um, "upper_width_um": upper_width_um, "dielectric_thickness_nm": dielectric_thickness_nm, "overlap_um": overlap_um}, "estimated_overlap_area_um2": upper_width_um * overlap_um}


def optimize_wirebond_pads(*, current_ma: float, bondwire_count: int, edge_length_um: float, minimum_pitch_um: float = 100.0) -> dict[str, Any]:
    if current_ma <= 0.0 or bondwire_count < 1 or min(edge_length_um, minimum_pitch_um) <= 0.0:
        raise ValueError("Invalid wirebond requirements")
    maximum_count = max(1, int(edge_length_um // minimum_pitch_um))
    actual_count = min(bondwire_count, maximum_count)
    pitch = edge_length_um / actual_count
    return {"pad_count": actual_count, "pitch_um": pitch, "current_per_wire_ma": current_ma / actual_count, "pad_size_um": [max(80.0, pitch * 0.7), 100.0], "count_limited_by_edge": actual_count < bondwire_count}


def package_aware_placement(devices: list[dict[str, Any]], package: dict[str, Any]) -> dict[str, Any]:
    """Place RF devices near assigned package ports and DC devices inward."""
    width, height = float(package["width_um"]), float(package["height_um"])
    ports = package.get("ports", [])
    placements = []
    for index, device in enumerate(devices):
        if device.get("role") == "rf" and ports:
            port = ports[index % len(ports)]
            center = list(port["position_um"])
        else:
            angle = 2.0 * math.pi * index / max(len(devices), 1)
            center = [width / 2.0 + 0.2 * width * math.cos(angle), height / 2.0 + 0.2 * height * math.sin(angle)]
        placements.append({"device": device["name"], "center_um": center, "rotation_deg": device.get("rotation_deg", 0.0)})
    return {"schema": "text-to-gds.package-aware-placement.v1", "placements": placements}


def floorplan_chip(devices: list[dict[str, Any]], *, chip_width_um: float, chip_height_um: float, margin_um: float = 100.0) -> dict[str, Any]:
    """Deterministic shelf-packing floorplanner."""
    x = y = margin_um
    row_height = 0.0
    placements = []
    for device in sorted(devices, key=lambda item: float(item["height_um"]), reverse=True):
        width, height = float(device["width_um"]), float(device["height_um"])
        if x + width > chip_width_um - margin_um:
            x, y, row_height = margin_um, y + row_height + margin_um, 0.0
        if y + height > chip_height_um - margin_um:
            raise ValueError("Devices do not fit inside chip floorplan")
        placements.append({"device": device["name"], "bbox_um": [x, y, x + width, y + height]})
        x += width + margin_um
        row_height = max(row_height, height)
    return {"chip_bbox_um": [0.0, 0.0, chip_width_um, chip_height_um], "placements": placements}


def hierarchical_layout(name: str, instances: list[dict[str, Any]], ports: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"schema": "text-to-gds.hierarchical-layout.v1", "name": name, "instances": instances, "ports": ports or [], "instance_count": len(instances)}


def inherit_cell_parameters(base: dict[str, Any], overrides: dict[str, Any], *, name: str) -> dict[str, Any]:
    parameters = dict(base.get("parameters", {}))
    parameters.update(overrides)
    return {**base, "name": name, "parent": base.get("name"), "parameters": parameters}


def quantum_cell_library() -> dict[str, dict[str, Any]]:
    return {
        "jpa": {"pcell": "lumped_element_jpa_seed", "ports": ["input", "output", "flux"]},
        "jtwpa": {"pcell": "photonic_crystal_stwpa", "ports": ["input", "output", "pump"]},
        "twpa": {"pcell": "periodically_loaded_kit_unit_cell", "ports": ["input", "output"]},
        "transmon": {"pcell": "transmon_island", "ports": ["readout", "drive", "flux"]},
        "fluxonium": {"pcell": "fluxonium_loop", "ports": ["readout", "flux"]},
        "resonator": {"pcell": "cpw_straight", "ports": ["input", "output"]},
        "filter": {"pcell": "coupled_resonator_filter", "ports": ["input", "output"]},
        "coupler": {"pcell": "tunable_coupler", "ports": ["a", "b", "flux"]},
    }


def generate_layout_labels(instances: list[dict[str, Any]], *, prefix: str = "D") -> list[dict[str, Any]]:
    return [{"text": f"{prefix}{index + 1}_{instance.get('name', instance.get('device', 'CELL'))}", "position_um": instance.get("center_um", instance.get("position_um", [0.0, 0.0])), "layer": [10, 0]} for index, instance in enumerate(instances)]


def sem_alignment_mark(kind: str = "cross", *, size_um: float = 100.0, linewidth_um: float = 2.0) -> dict[str, Any]:
    if kind not in {"cross", "box_in_box", "vernier"}:
        raise ValueError("Unknown SEM alignment mark")
    return {"cell": f"sem_mark_{kind}", "size_um": size_um, "linewidth_um": linewidth_um, "layer": [101, 0]}
