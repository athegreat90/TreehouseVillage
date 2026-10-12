from __future__ import annotations

import gzip

import pytest

from treehouse_village.geometry.model import AABB, Block, Scene, Vec3
from treehouse_village.serialization.structure import StructureSerializer
from treehouse_village.serialization.segmentation import segment_scene, reconstruct_segments


def test_vec3_and_bounds_are_immutable_and_translate():
    origin = Vec3(2, -1, 4)
    assert origin + Vec3(-2, 3, 1) == Vec3(0, 2, 5)
    assert origin.translate(3, 4, -2) == Vec3(5, 3, 2)
    bounds = AABB(Vec3(0, 1, 2), Vec3(3, 5, 7))
    assert bounds.size == Vec3(4, 5, 6)
    assert bounds.contains(Vec3(3, 5, 7))
    assert not bounds.contains(Vec3(4, 5, 7))


def test_scene_rejects_conflicting_blocks_and_translates_deterministically():
    scene = Scene()
    scene.set_block(Vec3(1, 2, 3), Block("minecraft:stone"))
    scene.set_block(Vec3(2, 2, 3), Block("minecraft:lantern", {"hanging": "false"}))
    with pytest.raises(ValueError, match="conflicting block"):
        scene.set_block(Vec3(1, 2, 3), Block("minecraft:air"))
    moved = scene.translated(Vec3(-1, 0, 2))
    assert moved.blocks() == (
        (Vec3(0, 2, 5), Block("minecraft:stone")),
        (Vec3(1, 2, 5), Block("minecraft:lantern", {"hanging": "false"})),
    )


def test_structure_serialization_round_trips_java_wire_and_schema_keys():
    scene = Scene()
    scene.set_block(Vec3(4, 10, -2), Block("minecraft:jungle_log", {"axis": "y"}))
    scene.set_block(Vec3(4, 11, -2), Block("minecraft:lantern", {"hanging": "false"}))
    for data_version, keys in ((4903, ("Name", "Properties")), (5023, ("id", "properties"))):
        raw = StructureSerializer(data_version=data_version).dumps(scene)
        assert raw[:2] == b"\x1f\x8b"
        decoded = gzip.decompress(raw)
        assert keys[0].encode("ascii") in decoded
        assert keys[1].encode("ascii") in decoded
        assert b"minecraft:jungle_log" in decoded


def test_structure_size_is_list_of_ints_not_int_array():
    from rapidnbt import nbtio

    scene = Scene()
    scene.set_block(Vec3(1, 2, 3), Block("minecraft:stone"))
    root = nbtio.loads(StructureSerializer(data_version=5023).dumps(scene))
    assert root["size"].get_type().name == "List"
    assert all(child.get_type().name == "Int" for child in root["size"])


def test_structure_round_trips_through_rapidnbt():
    from rapidnbt import nbtio

    scene = Scene()
    scene.set_block(Vec3(1, 2, 3), Block("minecraft:stone"))
    root = nbtio.loads(StructureSerializer(data_version=5023).dumps(scene))
    assert int(root["DataVersion"]) == 5023
    assert len(root["blocks"]) == 1


def test_structure_serialization_is_deterministic_and_normalizes_origin():
    first = Scene()
    first.set_block(Vec3(20, 30, 40), Block("minecraft:stone"))
    first.set_block(Vec3(21, 30, 40), Block("minecraft:stone"))
    second = Scene()
    second.set_block(Vec3(21, 30, 40), Block("minecraft:stone"))
    second.set_block(Vec3(20, 30, 40), Block("minecraft:stone"))
    serializer = StructureSerializer(data_version=4903)
    assert serializer.dumps(first) == serializer.dumps(second)


def test_segmentation_reconstructs_without_gaps_or_overlaps():
    scene = Scene()
    for x in range(5):
        for y in range(3):
            for z in range(4):
                scene.set_block(Vec3(x, y, z), Block("minecraft:stone"))
    segments = segment_scene(scene, max_size=Vec3(2, 2, 2))
    assert len(segments) > 1
    assert reconstruct_segments(segments) == scene
    occupied = [position + segment.origin
                for segment in segments
                for position, _ in segment.scene.blocks()]
    assert len(occupied) == len(set(occupied))
