from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..geometry.model import AABB, Block, Scene, Vec3
from .contracts import BuildingSpec, CoverageRequirement, FixtureRequirement


@dataclass(frozen=True)
class CivicDesign:
    identifier: str
    width: int
    depth: int
    height: int
    floor_block: str
    wall_block: str
    roof_block: str
    door_block: str
    fixture_blocks: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.width < 7 or self.depth < 7 or self.width % 2 == 0 or self.depth % 2 == 0:
            raise ValueError("civic width and depth must be odd integers of at least 7")
        if self.height < 4:
            raise ValueError("civic height must be at least 4")
        for name in (self.floor_block, self.wall_block, self.roof_block, self.door_block):
            if not name.startswith("minecraft:"):
                raise ValueError(f"civic blocks must be namespaced: {name}")
        for block in self.fixture_blocks.values():
            if not block.startswith("minecraft:"):
                raise ValueError(f"civic fixture blocks must be namespaced: {block}")


@dataclass(frozen=True)
class CivicAssembly:
    design: CivicDesign
    scene: Scene
    spec: BuildingSpec


def _fixture(pos: Vec3, name: str, block: str, prop: Mapping[str, str] = ()) -> FixtureRequirement:
    return FixtureRequirement(name, pos, block, prop)


_CIVIC_DESIGNS = {
    "library_enchanting": CivicDesign(
        "library_enchanting", 9, 9, 6,
        "minecraft:spruce_planks", "minecraft:spruce_planks", "minecraft:spruce_planks", "minecraft:spruce_door",
        {"enchanting_table": "minecraft:enchanting_table", "lectern": "minecraft:lectern",
         "bookshelf": "minecraft:bookshelf", "lantern": "minecraft:lantern"},
    ),
    "suspended_marketplace": CivicDesign(
        "suspended_marketplace", 11, 9, 5,
        "minecraft:jungle_planks", "minecraft:jungle_planks", "minecraft:jungle_planks", "minecraft:jungle_door",
        {"barrel": "minecraft:barrel", "crate": "minecraft:barrel", "sign": "minecraft:oak_hanging_sign",
         "awning": "minecraft:red_wool"},
    ),
    "crafting_workshop": CivicDesign(
        "crafting_workshop", 9, 9, 5,
        "minecraft:dark_oak_planks", "minecraft:dark_oak_planks", "minecraft:dark_oak_planks", "minecraft:dark_oak_door",
        {"crafting_table": "minecraft:crafting_table", "furnace": "minecraft:furnace",
         "blast_furnace": "minecraft:blast_furnace", "smoker": "minecraft:smoker",
         "anvil": "minecraft:anvil", "smithing_table": "minecraft:smithing_table",
         "stonecutter": "minecraft:stonecutter"},
    ),
    "storage_warehouse": CivicDesign(
        "storage_warehouse", 11, 11, 6,
        "minecraft:birch_planks", "minecraft:birch_planks", "minecraft:birch_planks", "minecraft:birch_door",
        {"chest": "minecraft:chest", "barrel": "minecraft:barrel", "lantern": "minecraft:lantern"},
    ),
    "alchemy_hut": CivicDesign(
        "alchemy_hut", 7, 7, 5,
        "minecraft:mangrove_planks", "minecraft:mangrove_planks", "minecraft:mangrove_planks", "minecraft:mangrove_door",
        {"brewing_stand": "minecraft:brewing_stand", "cauldron": "minecraft:cauldron",
         "shelf": "minecraft:oak_shelf", "lantern": "minecraft:lantern"},
    ),
}
CIVIC_DESIGNS: Mapping[str, CivicDesign] = MappingProxyType(_CIVIC_DESIGNS)


def generate_civic(
    civic_id: str,
    *,
    seed: int = 0,
    origin: Vec3 = Vec3(0, 0, 0),
) -> CivicAssembly:
    try:
        design = CIVIC_DESIGNS[civic_id]
    except KeyError as error:
        raise ValueError(f"unknown civic design {civic_id!r}; choose one of {tuple(CIVIC_DESIGNS)}") from error

    scene = Scene()
    w, d, h = design.width, design.depth, design.height

    def world(local):
        return local + origin
    def put(local, block):
        pos = world(local)
        scene.set_block(pos, block)
        return pos

    floor_cells = []
    wall_cells = []
    roof_cells = []
    walkway_cells = []

    door_x = w // 2
    # floor + foundation
    for x in range(w):
        for z in range(d):
            put(Vec3(x, 0, z), Block(design.floor_block))
            floor_cells.append(world(Vec3(x, 0, z)))
            walkway_cells.append(world(Vec3(x, 0, z)))

    # walls perimeter
    for x in range(w):
        for z in (0, d - 1):
            for y in range(1, h):
                if z == 0 and x == door_x and y in (1, 2):
                    continue
                put(Vec3(x, y, z), Block(design.wall_block))
                wall_cells.append(world(Vec3(x, y, z)))
    for z in range(1, d - 1):
        for x in (0, w - 1):
            for y in range(1, h):
                put(Vec3(x, y, z), Block(design.wall_block))
                wall_cells.append(world(Vec3(x, y, z)))

    # entrance door (center front)
    put(Vec3(door_x, 1, 0), Block(design.door_block, {"facing": "north", "half": "lower"}))
    put(Vec3(door_x, 2, 0), Block(design.door_block, {"facing": "north", "half": "upper"}))

    # roof
    for x in range(w):
        for z in range(d):
            put(Vec3(x, h, z), Block(design.roof_block))
            roof_cells.append(world(Vec3(x, h, z)))

    # interior fixtures (spread along center line)
    fixtures = []
    idx = 0
    for name, block in design.fixture_blocks.items():
        attempt = 0
        while True:
            x = 2 + ((idx + attempt) % max(1, w - 4))
            z = 2 + (((idx * 2) + attempt) % max(1, d - 4))
            pos = Vec3(x, 1, z)
            if scene.get_block(world(pos)) is None:
                break
            attempt += 1
        put(pos, Block(block))
        fixtures.append(_fixture(world(pos), name, block))
        idx += 1

    spec = BuildingSpec(
        identifier=design.identifier,
        category="civic",
        footprint=AABB(world(Vec3(0,0,0)), world(Vec3(w-1, h, d-1))),
        entrance=world(Vec3(door_x, 1, 0)),
        fixtures=tuple(fixtures),
        coverage=(
            CoverageRequirement("floor", tuple(floor_cells)),
            CoverageRequirement("wall", tuple(wall_cells)),
            CoverageRequirement("roof", tuple(roof_cells)),
            CoverageRequirement("walkway", tuple(walkway_cells)),
        ),
    )
    return CivicAssembly(design=design, scene=scene, spec=spec)
