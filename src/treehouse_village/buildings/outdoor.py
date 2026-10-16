from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..geometry.model import AABB, Block, Scene, Vec3
from .contracts import BuildingSpec, CoverageRequirement, FixtureRequirement


@dataclass(frozen=True)
class OutdoorDesign:
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
        if self.width < 5 or self.depth < 5:
            raise ValueError("outdoor dimensions must be at least 5")
        if self.height < 3:
            raise ValueError("outdoor height must be at least 3")
        for name in (self.floor_block, self.wall_block, self.roof_block, self.door_block):
            if not name.startswith("minecraft:"):
                raise ValueError(f"outdoor blocks must be namespaced: {name}")
        for block in self.fixture_blocks.values():
            if not block.startswith("minecraft:"):
                raise ValueError(f"outdoor fixture blocks must be namespaced: {block}")


@dataclass(frozen=True)
class OutdoorAssembly:
    design: OutdoorDesign
    scene: Scene
    spec: BuildingSpec


_OUTDOOR_DESIGNS = {
    "hanging_farm": OutdoorDesign("hanging_farm", 9, 7, 4, "minecraft:farmland", "minecraft:oak_fence", "minecraft:oak_planks", "minecraft:oak_door",
        {"wheat": "minecraft:wheat", "carrot": "minecraft:carrots", "potato": "minecraft:potatoes", "cocoa": "minecraft:cocoa", "bamboo": "minecraft:bamboo", "melon": "minecraft:melon", "water": "minecraft:water"}),
    "suspended_marketplace": OutdoorDesign("suspended_marketplace", 11, 9, 5, "minecraft:jungle_planks", "minecraft:jungle_planks", "minecraft:jungle_planks", "minecraft:jungle_door",
        {"stall": "minecraft:barrel", "crate": "minecraft:barrel", "sign": "minecraft:oak_hanging_sign", "awning": "minecraft:red_wool", "plaza": "minecraft:stone"}),
    "sunset_observatory": OutdoorDesign("sunset_observatory", 7, 7, 9, "minecraft:spruce_planks", "minecraft:spruce_planks", "minecraft:spruce_planks", "minecraft:spruce_door",
        {"telescope": "minecraft:spyglass", "lantern": "minecraft:lantern", "seat": "minecraft:oak_stairs", "railing": "minecraft:oak_fence"}),
    "waterfall_sanctuary": OutdoorDesign("waterfall_sanctuary", 9, 9, 6, "minecraft:mossy_cobblestone", "minecraft:mossy_cobblestone", "minecraft:mossy_cobblestone", "minecraft:oak_door",
        {"water": "minecraft:water", "treasure": "minecraft:chest", "vine": "minecraft:vine", "lantern": "minecraft:lantern"}),
    "entrance_gate": OutdoorDesign("entrance_gate", 9, 5, 6, "minecraft:oak_planks", "minecraft:oak_log", "minecraft:oak_planks", "minecraft:oak_door",
        {"root": "minecraft:mangrove_roots", "lantern": "minecraft:lantern", "sign": "minecraft:oak_sign"}),
    "watchtower": OutdoorDesign("watchtower", 5, 5, 8, "minecraft:spruce_planks", "minecraft:spruce_log", "minecraft:spruce_planks", "minecraft:spruce_door",
        {"banner": "minecraft:white_banner", "lantern": "minecraft:lantern", "ladder": "minecraft:ladder"}),
}
OUTDOOR_DESIGNS: Mapping[str, OutdoorDesign] = MappingProxyType(_OUTDOOR_DESIGNS)


def generate_outdoor(outdoor_id: str, *, seed: int = 0, origin: Vec3 = Vec3(0, 0, 0)) -> OutdoorAssembly:
    try:
        design = OUTDOOR_DESIGNS[outdoor_id]
    except KeyError as error:
        raise ValueError(f"unknown outdoor design {outdoor_id!r}; choose one of {tuple(OUTDOOR_DESIGNS)}") from error

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
    # S8: the basin is carved out of the floor first; containment and
    # support geometry (floor, walls, roof) is then built around it, and
    # the water source itself is only placed afterwards in the fixture
    # pass below — never before the geometry that contains it.
    water_local: Vec3 | None = None
    if any(block == "minecraft:water" for block in design.fixture_blocks.values()):
        water_local = Vec3(w // 2 - 1, 0, d // 2)

    for x in range(w):
        for z in range(d):
            position = Vec3(x, 0, z)
            if position != water_local:
                put(position, Block(design.floor_block))
            floor_cells.append(world(position))
            walkway_cells.append(world(position))

    # walls perimeter, leaving door gap
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

    # door
    put(Vec3(door_x, 1, 0), Block(design.door_block, {"facing": "north", "half": "lower"}))
    put(Vec3(door_x, 2, 0), Block(design.door_block, {"facing": "north", "half": "upper"}))

    # roof (only if height >=4)
    for x in range(w):
        for z in range(d):
            put(Vec3(x, h, z), Block(design.roof_block))
            roof_cells.append(world(Vec3(x, h, z)))

    fixtures = []
    idx = 0
    for name, block in design.fixture_blocks.items():
        if block == "minecraft:water" and water_local is not None:
            # S8: only now, with the basin and all geometry in place, does
            # the water source go in — embedded in the floor it was carved
            # from, so all four horizontal sides are floor blocks.
            put(water_local, Block(block))
            fixtures.append(FixtureRequirement(name, world(water_local), block))
            continue
        attempt = 0
        while True:
            x = 1 + ((idx + attempt) % max(1, w - 2))
            z = 1 + (((idx * 2) + attempt) % max(1, d - 2))
            pos = Vec3(x, 1, z)
            above_basin = (water_local is not None
                           and x == water_local.x and z == water_local.z)
            if not above_basin and scene.get_block(world(pos)) is None:
                break
            attempt += 1
        put(pos, Block(block))
        fixtures.append(FixtureRequirement(name, world(pos), block))

    spec = BuildingSpec(
        identifier=design.identifier,
        category="outdoor",
        footprint=AABB(world(Vec3(0, 0, 0)), world(Vec3(w - 1, h, d - 1))),
        entrance=world(Vec3(door_x, 1, 0)),
        fixtures=tuple(fixtures),
        coverage=(
            CoverageRequirement("floor", tuple(floor_cells)),
            CoverageRequirement("wall", tuple(wall_cells)),
            CoverageRequirement("roof", tuple(roof_cells)),
            CoverageRequirement("walkway", tuple(walkway_cells)),
        ),
    )
    return OutdoorAssembly(design=design, scene=scene, spec=spec)
