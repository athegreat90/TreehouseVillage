"""Deterministic composition of a complete village from declarative config.

Every element (trees, buildings, bridges, ground plane) is generated in
isolation and merged into one sparse scene. A merge never overwrites a
foreign block: any cell claimed twice with different blocks is reported as
a composition conflict so the configuration is fixed instead of the
geometry being silently patched.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bridges import BridgeAssembly, BridgeSpec, generate_bridge
from .buildings import (BuildingSpec, generate_civic, generate_home,
                        generate_outdoor, generate_village_hall)
from .config import CompactConfig, MegaConfig, VillageConfig
from .environment import place_environment
from .generator import TreeAssembly, TreeSpec, generate_tree
from .geometry.model import Block, Scene, Vec3
from .routes import RouteGraph

_BUILDING_GENERATORS = {
    "home": generate_home,
    "civic": generate_civic,
    "outdoor": generate_outdoor,
}


@dataclass(frozen=True)
class Village:
    """A fully composed village ready for validation and serialization."""

    config: VillageConfig
    trees: tuple[TreeAssembly, ...]
    buildings: tuple[BuildingSpec, ...]
    bridges: tuple[BridgeAssembly, ...]
    scene: Scene
    graph: RouteGraph


# Backwards-compatible alias used by the Compact integration suite.
CompactVillage = Village


def _merge(target: Scene, overlay: Scene, label: str) -> None:
    """Merge overlay into target, reporting every conflicting cell at once."""
    conflicts = []
    for position, block in overlay.blocks():
        existing = target.get_block(position)
        if existing is not None and existing != block:
            conflicts.append(f"{position}: {existing.name} vs {block.name}")
    if conflicts:
        shown = "; ".join(conflicts[:8])
        raise ValueError(
            f"composition conflict in {label} ({len(conflicts)} cells): {shown}")
    for position, block in overlay.blocks():
        target.set_block(position, block)


def generate_village(config: VillageConfig) -> Village:
    """Compose the complete village scene and its route graph.

    Order matters: structures claim their cells first, then the ground
    plane fills only the still-empty y=0 cells of the footprint, so grass
    never covers a floor, trunk or path and never overwrites a fixture.
    """
    scene = Scene()

    trees: list[TreeAssembly] = []
    for placement in config.trees:
        assembly = generate_tree(TreeSpec(
            origin=placement.origin,
            height=placement.height,
            seed=placement.seed,
            platform_level=placement.platform_level,
            platform_radius=placement.radius,
        ))
        _merge(scene, assembly.scene, placement.name)
        trees.append(assembly)

    buildings: list[BuildingSpec] = []
    node_positions: dict[str, Vec3] = {}
    for index, placement in enumerate(config.buildings):
        if placement.kind == "hall":
            assembly = generate_village_hall(seed=config.seed + index,
                                             origin=placement.origin)
        else:
            generator = _BUILDING_GENERATORS[placement.kind]
            assembly = generator(placement.design, seed=config.seed + index,
                                 origin=placement.origin)
        _merge(scene, assembly.scene, placement.node)
        buildings.append(assembly.spec)
        node_positions[placement.node] = placement.node_position or assembly.spec.entrance

    bridges: list[BridgeAssembly] = []
    for placement in config.bridges:
        spec = BridgeSpec(start=placement.start, end=placement.end,
                          width=placement.width)
        assembly = generate_bridge(spec)
        label = placement.name or f"bridge_{len(bridges) + 1}"
        _merge(scene, assembly.scene, label)
        bridges.append(assembly)
        # Both endpoints must sit on an occupied platform or deck cell:
        # the bridge writes only the interior span between them.
        for endpoint in (placement.start, placement.end):
            if scene.get_block(endpoint) is None:
                raise ValueError(
                    f"bridge {label}: endpoint {endpoint} is not an occupied platform cell")

    # Ground plane: prepared site, filling only empty footprint cells at y=0.
    for x in range(config.width):
        for z in range(config.depth):
            position = Vec3(x, 0, z)
            if scene.get_block(position) is None:
                scene.set_block(position, Block(config.ground_block))

    # M9: gardens and lamp posts on the prepared grass. Both route nodes and
    # every building entrance keep their approach cells clear (S9), so decor
    # can never sever the walks that validate_routes later proves.
    place_environment(
        scene, width=config.width, depth=config.depth,
        ground_block=config.ground_block,
        nodes=tuple(node_positions.values()) +
        tuple(spec.entrance for spec in buildings),
        seed=config.seed,
    )

    bounds = scene.bounds
    if bounds is None:
        raise ValueError("village composition produced an empty scene")
    if (bounds.minimum.x < 0 or bounds.maximum.x >= config.width or
            bounds.minimum.z < 0 or bounds.maximum.z >= config.depth):
        raise ValueError(
            f"composition exceeds the {config.width}x{config.depth} footprint: {bounds}")
    if bounds.minimum.y < 0:
        raise ValueError(f"composition reaches below y=0: {bounds}")

    for tree in config.trees:
        node_positions[tree.name] = tree.node_position

    hall_node = next((b.node for b in config.buildings if b.kind == "hall"),
                     config.entrance)
    edges = tuple(
        [(config.entrance, building.node)
         for building in config.buildings if building.node != config.entrance] +
        [(hall_node, tree.name) for tree in config.trees]
    )
    graph = RouteGraph(
        nodes=tuple((name, node_positions[name]) for name in config.node_names),
        edges=edges,
    )
    return Village(
        config=config,
        trees=tuple(trees),
        buildings=tuple(buildings),
        bridges=tuple(bridges),
        scene=scene,
        graph=graph,
    )


def generate_compact_village(config: CompactConfig) -> Village:
    """Compose the 96x96 Compact village."""
    return generate_village(config)


def generate_mega_village(config: MegaConfig) -> Village:
    """Compose the 176x176 Mega village."""
    return generate_village(config)
