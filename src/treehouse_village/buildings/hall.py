from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..geometry.model import AABB, Block, Scene, Vec3
from .contracts import BuildingSpec, CoverageRequirement, FixtureRequirement


@dataclass(frozen=True)
class VillageHallDesign:
    """Material palette for the fixed-envelope Central Great Tree Village Hall.

    The hall is a landmark structure with a fixed structural envelope
    (15x15 footprint, six wall levels, balcony deck at y=7, observation
    platform at y=11); only the material palette is configurable.
    """

    identifier: str = "village_hall"
    width: int = 15
    depth: int = 15
    wall_height: int = 6
    floor_block: str = "minecraft:jungle_planks"
    wall_block: str = "minecraft:jungle_planks"
    frame_block: str = "minecraft:stripped_jungle_log"
    roof_block: str = "minecraft:jungle_planks"
    platform_block: str = "minecraft:spruce_planks"
    trunk_block: str = "minecraft:stripped_jungle_log"
    stair_block: str = "minecraft:jungle_stairs"
    fence_block: str = "minecraft:jungle_fence"
    leaf_block: str = "minecraft:jungle_leaves"
    window_block: str = "minecraft:glass"
    door_block: str = "minecraft:jungle_door"
    table_block: str = "minecraft:spruce_slab"
    table_leg_block: str = "minecraft:spruce_fence"
    lantern_block: str = "minecraft:lantern"
    chain_block: str = "minecraft:chain"

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.replace("_", "").isalnum():
            raise ValueError("hall identifier must contain lowercase letters, digits, and underscores")
        # The hall is a landmark with a fixed multi-level structural envelope;
        # other dimensions would silently break the spiral stairs and decks.
        if self.width != 15 or self.depth != 15:
            raise ValueError("village hall width and depth must both be 15")
        if self.wall_height != 6:
            raise ValueError("village hall wall_height must be 6")
        for name, value in vars(self).items():
            if name.endswith("_block") and not value.startswith("minecraft:"):
                raise ValueError(f"village hall blocks must be namespaced: {name}={value!r}")


@dataclass(frozen=True)
class VillageHallAssembly:
    design: VillageHallDesign
    scene: Scene
    spec: BuildingSpec
    bridge_anchors: tuple[Vec3, ...]


VILLAGE_HALL_DESIGN = VillageHallDesign()

# Structural sub-geometry of the fixed envelope (local coordinates).
_TRUNK_MIN, _TRUNK_MAX = 6, 8          # trunk footprint x/z range
_DECK_Y = 7                             # balcony deck / ground-hall ceiling
_PLATFORM_Y = 11                        # observation platform
_CENTER = 7
# Lower spiral run: ground hall -> balcony, hugging the trunk's south edge.
_LOWER_RUN = ((5, 9), (6, 9), (7, 9), (8, 9), (9, 9), (9, 8), (9, 7))
_LOWER_OPENING = (9, 8)                 # deck stairwell opening above step 6
# Upper spiral run: balcony -> observation platform, west of the trunk.
_UPPER_RUN = ((5, 9), (5, 8), (5, 7), (5, 6))
_UPPER_OPENING = (5, 7)                 # platform stairwell opening above step 3
_WINDOWS = frozenset({(2, 0), (12, 0), (4, 14), (10, 14),
                      (0, 4), (0, 10), (14, 4), (14, 10)})
_ANCHORS = ((0, 7), (7, 0), (7, 14), (14, 7))   # deck edge bridge anchors (x, z)
_CHANDELIERS = ((4, 4), (10, 4), (4, 10), (10, 10))
_GROUND_LIGHTS = ((1, 2), (13, 2), (1, 12), (13, 12))
_PLATFORM_CORNERS = ((4, 4), (4, 10), (10, 4), (10, 10))


def _trunk_cells(y_min: int, y_max: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (x, z)
        for y in range(y_min, y_max + 1)
        for x in range(_TRUNK_MIN, _TRUNK_MAX + 1)
        for z in range(_TRUNK_MIN, _TRUNK_MAX + 1)
    )


def generate_village_hall(
    *,
    design: VillageHallDesign = VILLAGE_HALL_DESIGN,
    seed: int = 0,
    origin: Vec3 = Vec3(0, 0, 0),
) -> VillageHallAssembly:
    """Build the multi-level Central Great Tree Village Hall.

    The hall wraps a massive trunk core with a ground meeting hall, two
    communal tables, four chandeliers, a spiral stair to the ring balcony,
    a second spiral to the open observation platform, railings, and four
    deck-edge bridge anchors for the suspension bridge network.
    """
    scene = Scene()
    fixtures: list[FixtureRequirement] = []
    floor_cells: list[Vec3] = []
    wall_cells: list[Vec3] = []
    roof_cells: list[Vec3] = []
    walkway_cells: list[Vec3] = []
    platform_cells: list[Vec3] = []
    stair_cells: list[Vec3] = []

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

    trunk = set(_trunk_cells(0, _PLATFORM_Y + 3))

    # Foundation plane; the trunk logs placed below also occupy their nine
    # floor cells, so the full 15x15 plane counts as floor coverage.
    for x in range(15):
        for z in range(15):
            floor_cells.append(world(Vec3(x, 0, z)))
    trunk_floor = set(_trunk_cells(0, 0))
    for x in range(15):
        for z in range(15):
            if (x, z) in trunk_floor:
                continue
            put(Vec3(x, 0, z), Block(design.floor_block))

    # Massive trunk core rising through every level.
    for x in range(_TRUNK_MIN, _TRUNK_MAX + 1):
        for z in range(_TRUNK_MIN, _TRUNK_MAX + 1):
            for y in range(0, 15):
                put(Vec3(x, y, z), Block(design.trunk_block, {"axis": "y"}))

    # Perimeter walls y=1..6 with a central door gap and eight window panes.
    door_lower = Vec3(_CENTER, 1, 0)
    door_upper = Vec3(_CENTER, 2, 0)
    door_states_lower = {"facing": "north", "half": "lower",
                         "hinge": "left", "open": "false", "powered": "false"}
    door_states_upper = {"facing": "north", "half": "upper",
                         "hinge": "left", "open": "false", "powered": "false"}
    window_positions: list[Vec3] = []
    for x in range(15):
        for z in range(15):
            if x not in (0, 14) and z not in (0, 14):
                continue
            for y in range(1, 7):
                local = Vec3(x, y, z)
                if local == door_lower:
                    put(local, Block(design.door_block, door_states_lower))
                    fixtures.append(FixtureRequirement("front_door_lower", world(local),
                                                       design.door_block, door_states_lower))
                elif local == door_upper:
                    put(local, Block(design.door_block, door_states_upper))
                    fixtures.append(FixtureRequirement("front_door_upper", world(local),
                                                       design.door_block, door_states_upper))
                elif y in (2, 3) and (x, z) in _WINDOWS:
                    window_positions.append(put(local, Block(design.window_block)))
                elif x in (0, 14) and z in (0, 14):
                    put(local, Block(design.frame_block, {"axis": "y"}))
                else:
                    name = design.wall_block
                    if (seed + x * 31 + z * 17 + y * 13) % 11 == 0:
                        name = design.frame_block
                    put(local, Block(name))
                wall_cells.append(world(local))

    for index, position in enumerate(window_positions):
        fixtures.append(FixtureRequirement(f"window_{index + 1}", position,
                                           design.window_block))

    # Balcony deck at y=7 roofs the meeting hall; the trunk passes through,
    # one cell stays open as the lower stairwell, and the top stair replaces
    # one plank. Coverage counts every occupied cell; only the intentional
    # opening stays uncovered.
    lower_top = Vec3(_LOWER_RUN[-1][0], _DECK_Y, _LOWER_RUN[-1][1])
    lower_open = Vec3(_LOWER_OPENING[0], _DECK_Y, _LOWER_OPENING[1])
    trunk_deck = set(_trunk_cells(_DECK_Y, _DECK_Y))
    for x in range(15):
        for z in range(15):
            local = Vec3(x, _DECK_Y, z)
            if local == lower_open:
                continue  # intentional stairwell opening
            roof_cells.append(world(local))
            if (x, z) in trunk_deck or local == lower_top:
                continue  # already occupied by trunk logs or the stair top
            walkway_cells.append(put(local, Block(design.roof_block)))

    # Lower spiral stair, ground hall -> balcony. Facings follow the
    # direction of travel; a fence column supports the floating top step.
    previous = (_CENTER, 15)  # virtual start south of the run
    for index, (x, z) in enumerate(_LOWER_RUN):
        y = index + 1
        dx = x - previous[0]
        dz = z - previous[1]
        facing = "east" if dx > 0 else "west" if dx < 0 else "north" if dz < 0 else "south"
        stair_cells.append(put(Vec3(x, y, z),
                               Block(design.stair_block, {"facing": facing,
                                                          "half": "lower",
                                                          "shape": "straight",
                                                          "waterlogged": "false"})))
        previous = (x, z)
    for y in range(1, _DECK_Y):
        put(Vec3(9, y, 7), Block(design.fence_block))

    # Ring railing on the balcony, open at the four bridge anchors.
    for x in range(15):
        for z in range(15):
            if x not in (0, 14) and z not in (0, 14):
                continue
            if (x, z) in _ANCHORS:
                continue
            put(Vec3(x, _DECK_Y + 1, z), Block(design.fence_block))

    # Upper spiral stair, balcony -> observation platform, with supports.
    upper_top = Vec3(_UPPER_RUN[-1][0], _PLATFORM_Y, _UPPER_RUN[-1][1])
    upper_open = Vec3(_UPPER_OPENING[0], _PLATFORM_Y, _UPPER_OPENING[1])
    previous = (_CENTER, 15)
    for index, (x, z) in enumerate(_UPPER_RUN):
        y = _DECK_Y + 1 + index
        dx = x - previous[0]
        dz = z - previous[1]
        facing = "east" if dx > 0 else "west" if dx < 0 else "north" if dz < 0 else "south"
        stair_cells.append(put(Vec3(x, y, z),
                               Block(design.stair_block, {"facing": facing,
                                                          "half": "lower",
                                                          "shape": "straight",
                                                          "waterlogged": "false"})))
        previous = (x, z)
    for x, z, ys in ((5, 8, (8,)), (5, 7, (8, 9)), (5, 6, (8, 9, 10))):
        for y in ys:
            put(Vec3(x, y, z), Block(design.fence_block))

    # Observation platform at y=11: planks around the trunk, one stairwell
    # opening, and the top stair replacing one plank. Coverage counts every
    # occupied cell; only the intentional opening stays uncovered.
    trunk_platform = set(_trunk_cells(_PLATFORM_Y, _PLATFORM_Y))
    for x in range(4, 11):
        for z in range(4, 11):
            local = Vec3(x, _PLATFORM_Y, z)
            if local == upper_open:
                continue  # intentional stairwell opening
            platform_cells.append(world(local))
            if (x, z) in trunk_platform or local == upper_top:
                continue  # already occupied by trunk logs or the stair top
            walkway_cells.append(put(local, Block(design.platform_block)))

    # Platform railing with lantern-topped corners.
    for x in range(4, 11):
        for z in range(4, 11):
            if x not in (4, 10) and z not in (4, 10):
                continue
            local = Vec3(x, _PLATFORM_Y + 1, z)
            if (x, z) in _PLATFORM_CORNERS:
                fixture(f"terrace_light_{_PLATFORM_CORNERS.index((x, z)) + 1}", local,
                        Block(design.lantern_block, {"hanging": "false",
                                                     "waterlogged": "false"}),
                        {"hanging": "false", "waterlogged": "false"})
            else:
                put(local, Block(design.fence_block))

    # Two long communal tables in the meeting hall.
    for table_name, x in (("communal_table_west", 3), ("communal_table_east", 11)):
        for z in range(4, 11):
            top = Vec3(x, 2, z)
            block = Block(design.table_block, {"type": "bottom", "waterlogged": "false"})
            position = put(top, block)
            if z == 7:
                fixtures.append(FixtureRequirement(table_name, position,
                                                   block.name, dict(block.properties)))
        for z in (4, 7, 10):
            put(Vec3(x, 1, z), Block(design.table_leg_block))

    # Four hanging chandeliers pinned to the deck by chains.
    for index, (x, z) in enumerate(_CHANDELIERS):
        fixture(f"chandelier_{index + 1}", Vec3(x, 4, z),
                Block(design.lantern_block, {"hanging": "true", "waterlogged": "false"}),
                {"hanging": "true", "waterlogged": "false"})
        for y in (5, 6):
            put(Vec3(x, y, z), Block(design.chain_block))

    # Ground lanterns along the hall walls.
    for index, (x, z) in enumerate(_GROUND_LIGHTS):
        fixture(f"ground_light_{index + 1}", Vec3(x, 1, z),
                Block(design.lantern_block, {"hanging": "false", "waterlogged": "false"}),
                {"hanging": "false", "waterlogged": "false"})

    # Treetop canopy above the trunk.
    for x in range(5, 10):
        for z in range(5, 10):
            put(Vec3(x, 15, z), Block(design.leaf_block))
    for x in range(6, 9):
        for z in range(6, 9):
            put(Vec3(x, 16, z), Block(design.leaf_block))

    bridge_anchors = tuple(world(Vec3(x, _DECK_Y, z)) for x, z in _ANCHORS)

    spec = BuildingSpec(
        identifier=design.identifier,
        category="landmark",
        footprint=AABB(world(Vec3(0, 0, 0)), world(Vec3(14, 16, 14))),
        entrance=world(door_lower),
        fixtures=tuple(fixtures),
        coverage=(
            CoverageRequirement("floor", tuple(floor_cells)),
            CoverageRequirement("wall", tuple(wall_cells)),
            CoverageRequirement("roof", tuple(roof_cells)),
            CoverageRequirement("walkway", tuple(walkway_cells)),
            CoverageRequirement("platform", tuple(platform_cells)),
            CoverageRequirement("stair", tuple(stair_cells)),
        ),
    )
    return VillageHallAssembly(design=design, scene=scene, spec=spec,
                               bridge_anchors=bridge_anchors)
