from __future__ import annotations

from treehouse_village.geometry.model import AABB, Block, Scene, Vec3
from treehouse_village.validation.structural import (
    find_walkable_route,
    validate_reserved_volumes,
    validate_supports,
)


def _floor(length: int) -> Scene:
    scene = Scene()
    for x in range(length):
        scene.set_block(Vec3(x, 0, 0), Block("minecraft:jungle_planks"))
    return scene


def test_supported_blocks_pass_and_floating_blocks_fail():
    supported = _floor(1)
    supported.set_block(Vec3(0, 1, 0), Block("minecraft:oak_log"))
    assert validate_supports(supported) == ()

    floating = Scene()
    floating.set_block(Vec3(0, 4, 0), Block("minecraft:oak_log"))
    issues = validate_supports(floating)
    assert [issue.code for issue in issues] == ["unsupported_block"]
    assert issues[0].position == Vec3(0, 4, 0)


def test_reserved_volume_collision_is_reported():
    scene = _floor(1)
    issues = validate_reserved_volumes(scene, (AABB(Vec3(0, 0, 0), Vec3(0, 1, 0)),))
    assert [(issue.code, issue.position) for issue in issues] == [
        ("reserved_collision", Vec3(0, 0, 0)),
    ]


def test_walkable_route_requires_floor_and_headroom():
    scene = _floor(4)
    route = find_walkable_route(scene, Vec3(0, 1, 0), Vec3(3, 1, 0))
    assert route[0] == Vec3(0, 1, 0)
    assert route[-1] == Vec3(3, 1, 0)
    assert len(route) == 4

    blocked = _floor(4)
    blocked.set_block(Vec3(2, 1, 0), Block("minecraft:oak_log"))
    assert find_walkable_route(blocked, Vec3(0, 1, 0), Vec3(3, 1, 0)) is None


def test_walkable_route_rejects_low_headroom():
    scene = _floor(2)
    scene.set_block(Vec3(1, 2, 0), Block("minecraft:oak_log"))
    assert find_walkable_route(scene, Vec3(0, 1, 0), Vec3(1, 1, 0)) is None
