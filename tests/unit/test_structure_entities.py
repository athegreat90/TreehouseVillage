from __future__ import annotations

import pytest
from rapidnbt import ByteTag, CompoundTag, FloatTag, IntTag, nbtio

from treehouse_village.geometry.model import Block, Scene, Vec3
from treehouse_village.serialization.structure import StructureEntity, StructureSerializer


def _item_frame(anchor: Vec3) -> StructureEntity:
    return StructureEntity(
        position=(anchor.x + 0.5, anchor.y + 0.5, anchor.z + 0.0625),
        block_position=anchor,
        nbt=CompoundTag({
            "id": "minecraft:item_frame",
            "Facing": ByteTag(2),
            "Fixed": ByteTag(0),
            "Invisible": ByteTag(0),
            "Item": CompoundTag({"id": "minecraft:emerald", "count": IntTag(1)}),
            "ItemDropChance": FloatTag(0.0),
            "ItemRotation": ByteTag(0),
        }),
    )


@pytest.mark.parametrize("data_version", [4790, 4903, 5023])
def test_item_frame_entity_uses_structure_entity_schema_and_relative_coordinates(data_version):
    anchor = Vec3(10, 20, -4)
    scene = Scene({anchor: Block("minecraft:jungle_planks")})
    entity = _item_frame(anchor)

    serialized = StructureSerializer(data_version=data_version).dumps(scene, entities=(entity,))
    root = nbtio.loads(serialized)

    assert len(root["entities"]) == 1
    record = root["entities"][0]
    assert [value.get_type().name for value in record["pos"]] == ["Double"] * 3
    assert [float(value) for value in record["pos"]] == [0.5, 0.5, 0.0625]
    assert [value.get_type().name for value in record["blockPos"]] == ["Int"] * 3
    assert [int(value) for value in record["blockPos"]] == [0, 0, 0]

    payload = record["nbt"]
    assert payload["id"].value == b"minecraft:item_frame"
    assert int(payload["Facing"]) == 2
    assert payload["Item"]["id"].value == b"minecraft:emerald"
    assert int(payload["Item"]["count"]) == 1
    assert payload["ItemDropChance"].get_type().name == "Float"
    assert int(payload["ItemRotation"]) == 0


def test_block_only_serialization_keeps_an_empty_entity_list():
    scene = Scene({Vec3(2, 3, 4): Block("minecraft:stone")})
    root = nbtio.loads(StructureSerializer(data_version=5023).dumps(scene))
    assert len(root["entities"]) == 0
    assert len(root["blocks"]) == 1


def test_structure_entity_anchor_must_be_occupied_by_the_scene():
    scene = Scene({Vec3(0, 0, 0): Block("minecraft:stone")})
    entity = _item_frame(Vec3(4, 0, 0))
    with pytest.raises(ValueError, match="entity block position.*scene bounds"):
        StructureSerializer(data_version=5023).dumps(scene, entities=(entity,))


def test_serialization_package_exports_entity_api_and_preserves_existing_exports():
    from treehouse_village.serialization import (
        Segment,
        StructureEntity as ExportedStructureEntity,
        StructureSerializer as ExportedStructureSerializer,
        reconstruct_segments,
        segment_scene,
    )

    assert ExportedStructureEntity is StructureEntity
    assert ExportedStructureSerializer is StructureSerializer
    assert Segment is not None
    assert callable(reconstruct_segments)
    assert callable(segment_scene)
