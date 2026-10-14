"""T4e: Central Great Tree Village Hall — the landmark hall building."""

import pytest

from treehouse_village.buildings import (
    VILLAGE_HALL_DESIGN,
    VillageHallAssembly,
    VillageHallDesign,
    generate_village_hall,
    validate_building,
)
from treehouse_village.geometry.model import Vec3
from treehouse_village.validation import find_walkable_route


def test_village_hall_generates_valid_contract():
    assembly = generate_village_hall()
    assert validate_building(assembly.scene, assembly.spec) == ()


def test_village_hall_design_rejects_invalid_dimensions():
    with pytest.raises(ValueError):
        VillageHallDesign(width=13, depth=15)
    with pytest.raises(ValueError):
        VillageHallDesign(width=15, depth=15, wall_height=3)
    with pytest.raises(ValueError):
        VillageHallDesign(floor_block="jungle_planks")


def test_village_hall_is_multi_level():
    scene = generate_village_hall().scene
    for y in (0, 1, 4, 7, 11, 12, 14, 15, 16):
        assert any(p.y == y for p, _ in scene.blocks()), f"missing level y={y}"
    # Standing cells stay clear at every inhabited level.
    for position in (Vec3(7, 1, 1), Vec3(9, 8, 7), Vec3(6, 12, 9), Vec3(5, 12, 5)):
        assert scene.get_block(position) is None


def test_village_hall_trunk_rises_through_every_level():
    scene = generate_village_hall().scene
    for y in range(0, 15):
        for x in range(6, 9):
            for z in range(6, 9):
                block = scene.get_block(Vec3(x, y, z))
                assert block is not None and block.name == "minecraft:stripped_jungle_log"


def test_village_hall_spiral_stairs_connect_levels():
    assembly = generate_village_hall()
    stairs = {p: b for p, b in assembly.scene.blocks()
              if b.name == "minecraft:jungle_stairs"}
    assert len(stairs) == 11
    lower = sorted((p for p in stairs if p.y <= 7), key=lambda p: p.y)
    upper = sorted((p for p in stairs if p.y >= 8), key=lambda p: p.y)
    assert [p.y for p in lower] == [1, 2, 3, 4, 5, 6, 7]
    assert [p.y for p in upper] == [8, 9, 10, 11]
    for run in (lower, upper):
        for a, b in zip(run, run[1:]):
            assert b.y == a.y + 1
            assert abs(b.x - a.x) + abs(b.z - a.z) == 1
    for block in stairs.values():
        assert dict(block.properties).get("facing") in {"north", "south", "east", "west"}


def test_village_hall_bridge_anchors_are_clear_deck_edges():
    assembly = generate_village_hall()
    assert tuple(sorted(assembly.bridge_anchors)) == (
        Vec3(0, 7, 7), Vec3(7, 7, 0), Vec3(7, 7, 14), Vec3(14, 7, 7))
    scene = assembly.scene
    for anchor in assembly.bridge_anchors:
        assert scene.get_block(anchor) is not None  # deck cell occupied
        standing = anchor.translate(0, 1, 0)
        assert scene.get_block(standing) is None
        assert scene.get_block(standing.translate(0, 1, 0)) is None  # headroom


def test_village_hall_routes_reach_every_level():
    scene = generate_village_hall().scene
    # Ground hall: entrance to both communal tables.
    assert find_walkable_route(scene, Vec3(7, 1, 1), Vec3(2, 1, 7)) is not None
    assert find_walkable_route(scene, Vec3(7, 1, 1), Vec3(12, 1, 7)) is not None
    # Balcony: stair arrival to all four bridge anchor gaps.
    assert find_walkable_route(scene, Vec3(9, 8, 7), Vec3(7, 8, 0)) is not None
    assert find_walkable_route(scene, Vec3(9, 8, 7), Vec3(7, 8, 14)) is not None
    assert find_walkable_route(scene, Vec3(9, 8, 7), Vec3(0, 8, 7)) is not None
    assert find_walkable_route(scene, Vec3(9, 8, 7), Vec3(14, 8, 7)) is not None
    # Observation platform ring around the treetop.
    assert find_walkable_route(scene, Vec3(6, 12, 9), Vec3(5, 12, 5)) is not None
    assert find_walkable_route(scene, Vec3(6, 12, 9), Vec3(9, 12, 7)) is not None


def test_village_hall_chandeliers_hang_from_the_ceiling():
    scene = generate_village_hall().scene
    for x, z in ((4, 4), (10, 4), (4, 10), (10, 10)):
        lantern = scene.get_block(Vec3(x, 4, z))
        assert lantern is not None and lantern.name == "minecraft:lantern"
        assert dict(lantern.properties)["hanging"] == "true"
        for y in (5, 6):
            chain = scene.get_block(Vec3(x, y, z))
            assert chain is not None and chain.name == "minecraft:chain"


def test_village_hall_communal_tables_and_door_states():
    assembly = generate_village_hall()
    scene = assembly.scene
    names = {f.name for f in assembly.spec.fixtures}
    assert {"front_door_lower", "front_door_upper",
            "communal_table_west", "communal_table_east"} <= names
    door = scene.get_block(Vec3(7, 1, 0))
    assert door.name == "minecraft:jungle_door"
    assert dict(door.properties)["facing"] == "north"
    for x in (3, 11):
        for z in range(4, 11):
            top = scene.get_block(Vec3(x, 2, z))
            assert top is not None and top.name == "minecraft:spruce_slab"
            assert dict(top.properties)["type"] == "bottom"
        for z in (4, 7, 10):
            leg = scene.get_block(Vec3(x, 1, z))
            assert leg is not None and leg.name == "minecraft:spruce_fence"


def test_village_hall_walls_complete_with_windows():
    assembly = generate_village_hall()
    walls = next(c for c in assembly.spec.coverage if c.name == "wall")
    assert len(walls.positions) == 336  # 56 perimeter cells x 6 levels
    scene = assembly.scene
    for x, z in ((2, 0), (12, 0), (4, 14), (10, 14), (0, 4), (0, 10), (14, 4), (14, 10)):
        for y in (2, 3):
            pane = scene.get_block(Vec3(x, y, z))
            assert pane is not None and pane.name == "minecraft:glass"


def test_village_hall_coverage_masks_are_complete():
    assembly = generate_village_hall()
    masks = {c.name: c for c in assembly.spec.coverage}
    assert set(masks) == {"floor", "wall", "roof", "walkway", "platform", "stair"}
    assert len(masks["floor"].positions) == 225
    assert len(masks["roof"].positions) == 224   # 225 minus the lower stairwell opening
    assert len(masks["platform"].positions) == 48  # 7x7: 38 planks + 9 trunk + 1 top stair
    assert len(masks["stair"].positions) == 11
    assert len(masks["walkway"].positions) == 252  # deck planks 214 + platform planks 38


def test_village_hall_deck_and_platform_topology():
    scene = generate_village_hall().scene
    for level, expected in ((7, 224), (11, 48)):
        occupied = {p for p, _ in scene.blocks() if p.y == level}
        assert len(occupied) == expected
        supported = {p for p in occupied
                     if scene.get_block(p.translate(0, -1, 0)) is not None}
        assert supported, f"no directly supported cell at y={level}"
        reached = set(supported)
        frontier = list(supported)
        while frontier:
            current = frontier.pop()
            for offset in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)):
                neighbor = current.translate(*offset)
                if neighbor in occupied and neighbor not in reached:
                    reached.add(neighbor)
                    frontier.append(neighbor)
        assert reached == occupied, f"disconnected cells at y={level}"


def test_village_hall_deterministic():
    assert generate_village_hall(seed=3).scene == generate_village_hall(seed=3).scene


def test_village_hall_origin_relative():
    assembly = generate_village_hall(origin=Vec3(100, 40, -20))
    assert assembly.spec.entrance == Vec3(107, 41, -20)
    for position, _ in assembly.scene.blocks():
        assert assembly.spec.footprint.contains(position)


def test_village_hall_package_exports():
    import treehouse_village.buildings as buildings
    for name in ("VILLAGE_HALL_DESIGN", "VillageHallAssembly",
                 "VillageHallDesign", "generate_village_hall"):
        assert hasattr(buildings, name)


def test_village_hall_default_design_is_the_village_hall():
    assert VILLAGE_HALL_DESIGN.identifier == "village_hall"
