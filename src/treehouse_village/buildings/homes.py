from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..geometry.model import AABB, Block, Scene, Vec3
from .contracts import BuildingSpec, CoverageRequirement, FixtureRequirement


@dataclass(frozen=True)
class HomeDesign:
    """Palette and dimensions for one complete, composable residential home."""

    identifier: str
    width: int
    depth: int
    roof_style: str
    floor_block: str
    wall_block: str
    frame_block: str
    roof_block: str
    accent_block: str
    door_block: str
    bed_block: str
    porch_width: int
    porch_depth: int
    window_block: str = "minecraft:glass"
    storage_block: str = "minecraft:barrel"
    crafting_block: str = "minecraft:crafting_table"

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.replace("_", "").isalnum():
            raise ValueError("home identifier must contain lowercase letters, digits, and underscores")
        if self.width < 7 or self.depth < 7 or self.width % 2 == 0 or self.depth % 2 == 0:
            raise ValueError("home width and depth must be odd integers of at least 7")
        if self.porch_width < 3 or self.porch_width % 2 == 0 or self.porch_width > self.width - 2:
            raise ValueError("porch_width must be odd, at least 3, and narrower than the home")
        if self.porch_depth < 1:
            raise ValueError("porch_depth must be positive")
        if self.roof_style not in {"gable", "hip", "shed", "terrace"}:
            raise ValueError(f"unsupported roof style: {self.roof_style}")
        for name in (
            self.floor_block, self.wall_block, self.frame_block, self.roof_block,
            self.accent_block, self.door_block, self.bed_block, self.window_block,
            self.storage_block, self.crafting_block,
        ):
            if not name.startswith("minecraft:"):
                raise ValueError(f"home blocks must be namespaced: {name}")


@dataclass(frozen=True)
class HomeAssembly:
    design: HomeDesign
    scene: Scene
    spec: BuildingSpec


_HOME_DESIGNS = {
    "canopy_bungalow": HomeDesign(
        "canopy_bungalow", 7, 7, "gable", "minecraft:jungle_planks",
        "minecraft:jungle_planks", "minecraft:jungle_log", "minecraft:jungle_planks",
        "minecraft:stripped_jungle_log", "minecraft:jungle_door", "minecraft:white_bed", 5, 2,
    ),
    "bamboo_veranda": HomeDesign(
        "bamboo_veranda", 9, 7, "hip", "minecraft:bamboo_planks",
        "minecraft:bamboo_mosaic", "minecraft:stripped_bamboo_block", "minecraft:bamboo_planks",
        "minecraft:bamboo_block", "minecraft:bamboo_door", "minecraft:light_blue_bed", 7, 3,
    ),
    "spruce_branch_cottage": HomeDesign(
        "spruce_branch_cottage", 7, 9, "shed", "minecraft:spruce_planks",
        "minecraft:spruce_planks", "minecraft:stripped_spruce_log", "minecraft:dark_oak_planks",
        "minecraft:spruce_log", "minecraft:spruce_door", "minecraft:lime_bed", 5, 3,
    ),
    "orchid_terrace_house": HomeDesign(
        "orchid_terrace_house", 9, 9, "terrace", "minecraft:acacia_planks",
        "minecraft:dark_oak_planks", "minecraft:stripped_acacia_log", "minecraft:acacia_planks",
        "minecraft:dark_oak_planks", "minecraft:acacia_door", "minecraft:magenta_bed", 7, 2,
    ),
}
HOME_DESIGNS: Mapping[str, HomeDesign] = MappingProxyType(_HOME_DESIGNS)


def _roof_top(design: HomeDesign, x: int, z: int) -> int:
    if design.roof_style == "gable":
        rise = design.width // 2 - abs(x - design.width // 2)
        return 4 + rise
    if design.roof_style == "hip":
        inset = min(x, design.width - 1 - x, z, design.depth - 1 - z)
        return 4 + min(inset, 2)
    if design.roof_style == "shed":
        return 4 + (design.width - 1 - x) // 2
    return 4


def generate_home(
    home_id: str,
    *,
    seed: int = 0,
    origin: Vec3 = Vec3(0, 0, 0),
) -> HomeAssembly:
    """Build one fully furnished house in origin-relative block coordinates."""
    try:
        design = HOME_DESIGNS[home_id]
    except KeyError as error:
        raise ValueError(f"unknown home design {home_id!r}; choose one of {tuple(HOME_DESIGNS)}") from error

    scene = Scene()
    fixtures: list[FixtureRequirement] = []
    floor_cells: list[Vec3] = []
    wall_cells: list[Vec3] = []
    roof_cells: set[Vec3] = set()
    walkway_cells: list[Vec3] = []

    def world(local: Vec3) -> Vec3:
        return local + origin

    def put(local: Vec3, block: Block) -> Vec3:
        position = world(local)
        scene.set_block(position, block)
        return position

    def fixture(name: str, local: Vec3, block: Block,
                required: Mapping[str, str] = ()) -> Vec3:
        position = put(local, block)
        fixtures.append(FixtureRequirement(name, position, block.name, required))
        return position

    # Continuous plank floor and foundation plane; the porch is a separate,
    # continuous walkway extending directly from the entrance.
    for x in range(design.width):
        for z in range(design.depth):
            position = put(Vec3(x, 0, z), Block(design.floor_block))
            floor_cells.append(position)

    porch_left = (design.width - design.porch_width) // 2
    porch_right = porch_left + design.porch_width - 1
    for x in range(porch_left, porch_right + 1):
        for z in range(-design.porch_depth, 0):
            walkway_cells.append(put(Vec3(x, 0, z), Block(design.floor_block)))

    center_x = design.width // 2
    door_lower = Vec3(center_x, 1, 0)
    door_upper = Vec3(center_x, 2, 0)
    door_states_lower = {
        "facing": "north", "half": "lower", "hinge": "left",
        "open": "false", "powered": "false",
    }
    door_states_upper = {
        "facing": "north", "half": "upper", "hinge": "left",
        "open": "false", "powered": "false",
    }

    window_coords = {
        (0, 2),
        (design.width - 1, design.depth - 3),
        (2, design.depth - 1),
        (design.width - 3, design.depth - 1),
    }
    window_positions: list[Vec3] = []
    for x in range(design.width):
        for z in range(design.depth):
            if x not in (0, design.width - 1) and z not in (0, design.depth - 1):
                continue
            for y in (1, 2):
                local = Vec3(x, y, z)
                if local == door_lower:
                    put(local, Block(design.door_block, door_states_lower))
                    fixtures.append(FixtureRequirement("front_door_lower", world(local),
                                                       design.door_block, door_states_lower))
                elif local == door_upper:
                    put(local, Block(design.door_block, door_states_upper))
                    fixtures.append(FixtureRequirement("front_door_upper", world(local),
                                                       design.door_block, door_states_upper))
                elif y == 2 and (x, z) in window_coords:
                    position = put(local, Block(design.window_block))
                    window_positions.append(position)
                elif x in (0, design.width - 1) and z in (0, design.depth - 1):
                    put(local, Block(design.frame_block, {"axis": "y"}))
                else:
                    put(local, Block(design.wall_block))
                wall_cells.append(world(local))

    for index, position in enumerate(window_positions):
        fixtures.append(FixtureRequirement(f"window_{index + 1}", position, design.window_block))

    # The ceiling deck spans the room and supports every roof column. A
    # hanging lantern replaces one ceiling block and is pinned by the roof.
    interior_light = Vec3(center_x, 3, design.depth // 2)
    for x in range(design.width):
        for z in range(design.depth):
            local = Vec3(x, 3, z)
            roof_cells.add(world(local))
            if local == interior_light:
                fixture("interior_light", local,
                        Block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}),
                        {"hanging": "true", "waterlogged": "false"})
            else:
                put(local, Block(design.roof_block))

    # Solid supported roof columns prevent gaps and vary into four distinct
    # silhouettes. A seed-dependent accent changes only surface palette, not
    # mandatory component placement or room clearance.
    max_roof_y = 4
    for x in range(design.width):
        for z in range(design.depth):
            top = _roof_top(design, x, z)
            max_roof_y = max(max_roof_y, top)
            for y in range(4, top + 1):
                name = design.roof_block
                if y == top and (seed + x * 31 + z * 17) % 11 == 0:
                    name = design.accent_block
                roof_cells.add(put(Vec3(x, y, z), Block(name)))
    if design.roof_style == "terrace":
        for x in range(design.width):
            for z in range(design.depth):
                if x in (0, design.width - 1) or z in (0, design.depth - 1):
                    roof_cells.add(put(Vec3(x, 5, z), Block(design.accent_block)))
                    max_roof_y = max(max_roof_y, 5)

    # A real paired bed, storage barrel and crafting table occupy separate
    # supported floor cells and retain usable vanilla block states.
    bed_foot = Vec3(1, 1, design.depth - 3)
    bed_head = Vec3(1, 1, design.depth - 2)
    bed_facing = "south"
    bed_foot_states = {"part": "foot", "facing": bed_facing, "occupied": "false"}
    bed_head_states = {"part": "head", "facing": bed_facing, "occupied": "false"}
    fixture("bed_foot", bed_foot, Block(design.bed_block, bed_foot_states), bed_foot_states)
    fixture("bed_head", bed_head, Block(design.bed_block, bed_head_states), bed_head_states)
    fixture("storage", Vec3(design.width - 2, 1, 1),
            Block(design.storage_block, {"facing": "up", "open": "false"}),
            {"facing": "up", "open": "false"})
    fixture("crafting_table", Vec3(design.width - 2, 1, design.depth - 2),
            Block(design.crafting_block))

    # Fence rails border the porch but leave its centerline open. Lanterns
    # sit on the two supported corner posts and do not obstruct the entrance.
    for z in range(-design.porch_depth, 0):
        put(Vec3(porch_left, 1, z), Block("minecraft:jungle_fence"))
        put(Vec3(porch_right, 1, z), Block("minecraft:jungle_fence"))
    for x in range(porch_left, porch_right + 1):
        if x != center_x:
            put(Vec3(x, 1, -design.porch_depth), Block("minecraft:jungle_fence"))
    exterior_lights = (
        Vec3(porch_left, 2, -1),
        Vec3(porch_right, 2, -1),
    )
    for index, local in enumerate(exterior_lights):
        fixture("exterior_light" if index == 0 else "exterior_light_secondary", local,
                Block("minecraft:lantern", {"hanging": "false", "waterlogged": "false"}),
                {"hanging": "false", "waterlogged": "false"})

    spec = BuildingSpec(
        identifier=design.identifier,
        category="residential",
        footprint=AABB(
            world(Vec3(0, 0, -design.porch_depth)),
            world(Vec3(design.width - 1, max_roof_y, design.depth - 1)),
        ),
        entrance=world(door_lower),
        fixtures=tuple(fixtures),
        coverage=(
            CoverageRequirement("floor", tuple(floor_cells)),
            CoverageRequirement("wall", tuple(wall_cells)),
            CoverageRequirement("roof", tuple(roof_cells)),
            CoverageRequirement("walkway", tuple(walkway_cells)),
        ),
    )
    return HomeAssembly(design, scene, spec)
