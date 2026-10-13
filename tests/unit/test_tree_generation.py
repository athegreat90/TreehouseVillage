from __future__ import annotations

from treehouse_village.geometry.model import AABB, Block, Vec3
from treehouse_village.generator.trees import TreeSpec, generate_tree


def test_tree_generation_is_deterministic_for_same_seed():
    spec = TreeSpec(origin=Vec3(0, 0, 0), height=18, seed=7)
    first = generate_tree(spec)
    second = generate_tree(spec)
    assert first.scene == second.scene
    assert first.clearance == second.clearance


def test_tree_seed_changes_organic_geometry():
    first = generate_tree(TreeSpec(Vec3(0, 0, 0), height=18, seed=7))
    second = generate_tree(TreeSpec(Vec3(0, 0, 0), height=18, seed=8))
    assert first.scene != second.scene


def test_tree_has_supported_platform_and_required_materials():
    assembly = generate_tree(TreeSpec(Vec3(4, 0, -2), height=20, seed=11,
                                     platform_level=12, platform_radius=4))
    platform_y = 12
    platform = [
        (position, block) for position, block in assembly.scene.blocks()
        if position.y == platform_y and block.name == "minecraft:jungle_planks"
    ]
    supports = [
        position for position, block in assembly.scene.blocks()
        if position.y == platform_y - 1 and block.name == "minecraft:jungle_log"
    ]
    names = {block.name for _, block in assembly.scene.blocks()}
    assert len(platform) >= 20
    assert supports
    assert "minecraft:jungle_log" in names
    assert "minecraft:jungle_leaves" in names
    assert assembly.scene.bounds is not None


def test_tree_clearance_contains_no_foliage_or_platform_blocks():
    assembly = generate_tree(TreeSpec(Vec3(0, 0, 0), height=20, seed=5,
                                      platform_level=12, platform_radius=4))
    for position, block in assembly.scene.blocks():
        if assembly.clearance.contains(position):
            assert block.name not in {"minecraft:jungle_leaves", "minecraft:jungle_planks"}


def test_tree_respects_requested_origin_and_clearance_is_bounded():
    origin = Vec3(30, 5, -20)
    assembly = generate_tree(TreeSpec(origin, height=16, seed=3))
    assert assembly.scene.bounds is not None
    assert assembly.scene.bounds.minimum.x >= origin.x - 12
    assert assembly.scene.bounds.minimum.z >= origin.z - 12
    assert assembly.clearance.minimum.y == origin.y
    assert assembly.clearance.maximum.y < origin.y + 16
