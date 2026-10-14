"""Village route graph validated with 3D pathfinding over the actual scene.

Proximity between buildings proves nothing; a destination counts as reachable
only when a walkable route (with optional climbing/dropping) exists from the
village entrance to the node's standing cell.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry.model import Scene, Vec3
from .validation import find_walkable_route, is_walkable


@dataclass(frozen=True)
class RouteIssue:
    code: str
    node: str
    message: str


@dataclass(frozen=True)
class RouteGraph:
    """Named destinations as (name, standing cell) and declared connections."""

    nodes: tuple[tuple[str, Vec3], ...]
    edges: tuple[tuple[str, str], ...] = ()


def validate_routes(scene: Scene, graph: RouteGraph, entrance: str, *,
                    max_climb: int = 0,
                    max_drop: int = 0) -> tuple[RouteIssue, ...]:
    """Report every declared node that is unwalkable or unreachable.

    Edge endpoints must reference known nodes; edges themselves are
    informational because reachability is proven against the real scene
    geometry, not the declared connection list.
    """
    issues: list[RouteIssue] = []
    node_map: dict[str, Vec3] = {}
    for name, position in graph.nodes:
        if name in node_map:
            issues.append(RouteIssue(
                "duplicate_node", name,
                f"route graph declares node {name!r} more than once"))
        else:
            node_map[name] = position
    if issues:
        return tuple(issues)
    if entrance not in node_map:
        return (RouteIssue("unknown_entrance", entrance,
                           f"entrance {entrance!r} is not a route graph node"),)
    for source, target in graph.edges:
        for endpoint in (source, target):
            if endpoint not in node_map:
                issues.append(RouteIssue(
                    "unknown_edge_node", endpoint,
                    f"edge {source!r}->{target!r} references unknown node {endpoint!r}"))
    start = node_map[entrance]
    if not is_walkable(scene, start):
        issues.append(RouteIssue(
            "unwalkable_node", entrance,
            f"entrance {entrance!r} is not on a walkable cell"))
        return tuple(issues)
    for name, position in node_map.items():
        if name == entrance:
            continue
        if not is_walkable(scene, position):
            issues.append(RouteIssue(
                "unwalkable_node", name,
                f"node {name!r} is not on a walkable cell"))
            continue
        if find_walkable_route(scene, start, position,
                               max_climb=max_climb, max_drop=max_drop) is None:
            issues.append(RouteIssue(
                "unreachable_node", name,
                f"no walkable route from entrance {entrance!r} to {name!r}"))
    return tuple(issues)
