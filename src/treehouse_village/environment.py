"""Deterministic environment decor: garden flowers and lamp posts (M9).

Placement rules, all static and offline (no Minecraft run is claimed):

- decor only sits on the prepared ground plane: the cell below must be
  ``ground_block`` (never a structure floor, trunk cell or water) and the
  target cells must be empty;
- ``FLOWER_BLOCKS`` occupy one cell, ``LAMP_FENCE`` is topped by
  ``LAMP_LIGHT`` directly above it;
- nothing is placed within ``NODE_CLEARANCE`` blocks of a route node at
  the same height, so building-door approaches stay walkable (S9) and
  decor never severs the routes validated by ``validate_routes``;
- placement is pure arithmetic over (x, z) lattices — no randomness — so
  the same config+seed always reproduces the same geometry (S10).
"""

from __future__ import annotations

from .geometry.model import Block, Scene, Vec3

FLOWER_BLOCKS = ("minecraft:poppy", "minecraft:dandelion", "minecraft:cornflower")
LAMP_FENCE = "minecraft:dark_oak_fence"
LAMP_LIGHT = "minecraft:soul_lantern"
NODE_CLEARANCE = 3

# Isolated lattice points (never a continuous wall): flowers every 5 cells,
# lamps every 12 — gaps of open ground always remain for walking routes.
_FLOWER_STRIDE = 5
_LAMP_STRIDE = 12
_LAMP_OFFSET = 6


def place_environment(scene: Scene, *, width: int, depth: int,
                      ground_block: str, nodes: tuple[Vec3, ...] = (),
                      seed: int = 0) -> tuple[int, int]:
    """Add flowers and lamp posts to a prepared ground plane in place.

    Returns ``(flower_count, lamp_count)`` for diagnostics. ``nodes`` are
    route-graph node positions; only nodes at the decor height (y=1) can
    clear cells here, which covers every ground-level building entrance.
    """
    if width < 1 or depth < 1:
        raise ValueError("environment needs a positive footprint")

    cleared: set[tuple[int, int]] = set()
    for node in nodes:
        if node.y != 1:
            continue
        for dx in range(-NODE_CLEARANCE, NODE_CLEARANCE + 1):
            for dz in range(-NODE_CLEARANCE, NODE_CLEARANCE + 1):
                cleared.add((node.x + dx, node.z + dz))

    def grass(x: int, z: int) -> bool:
        ground = scene.get_block(Vec3(x, 0, z))
        return ground is not None and ground.name == ground_block

    def free(x: int, z: int, levels: tuple[int, ...]) -> bool:
        return all(scene.get_block(Vec3(x, y, z)) is None for y in levels)

    # Lamps first: they claim two cells, flowers then simply skip them.
    lamp_count = 0
    for x in range(_LAMP_OFFSET, width, _LAMP_STRIDE):
        for z in range(_LAMP_OFFSET, depth, _LAMP_STRIDE):
            if (x, z) in cleared or not grass(x, z) or not free(x, z, (1, 2)):
                continue
            scene.set_block(Vec3(x, 1, z), Block(LAMP_FENCE))
            scene.set_block(Vec3(x, 2, z), Block(LAMP_LIGHT))
            lamp_count += 1

    flower_count = 0
    start = (2 + (seed % _FLOWER_STRIDE)) % _FLOWER_STRIDE
    for x in range(start, width, _FLOWER_STRIDE):
        for z in range(start, depth, _FLOWER_STRIDE):
            if (x, z) in cleared or not grass(x, z) or not free(x, z, (1,)):
                continue
            flower = FLOWER_BLOCKS[(x * 31 + z * 17 + seed) % len(FLOWER_BLOCKS)]
            scene.set_block(Vec3(x, 1, z), Block(flower))
            flower_count += 1

    return flower_count, lamp_count
