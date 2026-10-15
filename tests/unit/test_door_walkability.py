"""Doors are passable in Minecraft: players walk through closed doors."""

from treehouse_village.geometry.model import Block, Scene, Vec3
from treehouse_village.validation import find_walkable_route, is_walkable


def _door_scene() -> Scene:
    scene = Scene()
    for x in range(3):
        for z in range(-1, 3):
            scene.set_block(Vec3(x, 0, z), Block("minecraft:jungle_planks"))
    # Solid walls flank the doorway so the door cell is the only connection.
    scene.set_block(Vec3(0, 1, 0), Block("minecraft:jungle_planks"))
    scene.set_block(Vec3(2, 1, 0), Block("minecraft:jungle_planks"))
    states_lower = {"facing": "north", "half": "lower", "hinge": "left",
                    "open": "false", "powered": "false"}
    states_upper = {"facing": "north", "half": "upper", "hinge": "left",
                    "open": "false", "powered": "false"}
    scene.set_block(Vec3(1, 1, 0), Block("minecraft:jungle_door", states_lower))
    scene.set_block(Vec3(1, 2, 0), Block("minecraft:jungle_door", states_upper))
    return scene


def test_door_cell_is_walkable():
    assert is_walkable(_door_scene(), Vec3(1, 1, 0))


def test_route_passes_through_a_closed_door():
    scene = _door_scene()
    route = find_walkable_route(scene, Vec3(1, 1, 1), Vec3(1, 1, -1))
    assert route is not None
    assert Vec3(1, 1, 0) in route


def test_solid_blocks_still_block_routes():
    scene = Scene()
    for x in range(3):
        for z in range(-1, 3):
            scene.set_block(Vec3(x, 0, z), Block("minecraft:jungle_planks"))
    # A solid plank wall replaces the doorway: no route exists.
    scene.set_block(Vec3(0, 1, 0), Block("minecraft:jungle_planks"))
    scene.set_block(Vec3(1, 1, 0), Block("minecraft:jungle_planks"))
    scene.set_block(Vec3(2, 1, 0), Block("minecraft:jungle_planks"))
    assert not is_walkable(scene, Vec3(1, 1, 0))
    assert find_walkable_route(scene, Vec3(1, 1, 1), Vec3(1, 1, -1)) is None


def test_hanging_lantern_still_blocks_headroom():
    scene = Scene()
    for x in range(2):
        for z in range(2):
            scene.set_block(Vec3(x, 0, z), Block("minecraft:jungle_planks"))
    scene.set_block(Vec3(0, 2, 0), Block("minecraft:lantern", {"hanging": "true"}))
    assert not is_walkable(scene, Vec3(0, 1, 0))
