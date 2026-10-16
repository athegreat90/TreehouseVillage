"""T9: environment — contained water plus deterministic gardens and lighting.

S8 requires containment and support geometry *before* any water source;
M9 adds gardens and lighting (the explicit sunset showcase lives in the
T8 datapack tests). Everything here is static geometry: no Minecraft run
and no in-game fluid tick is claimed.
"""

from pathlib import Path

import pytest

from treehouse_village.buildings import OUTDOOR_DESIGNS, generate_outdoor
from treehouse_village.config import CompactConfig, MegaConfig
from treehouse_village.geometry.model import Vec3
from treehouse_village.routes import validate_routes
from treehouse_village.validation import validate_water_containment
from treehouse_village.village import (CompactVillage, generate_compact_village,
                                       generate_mega_village)

ROOT = Path(__file__).resolve().parents[2]

WATER_DESIGNS = tuple(name for name, design in OUTDOOR_DESIGNS.items()
                      if "water" in design.fixture_blocks)


@pytest.fixture(scope="module")
def compact() -> CompactVillage:
    return generate_compact_village(CompactConfig.from_json(ROOT / "config" / "compact.json"))


@pytest.fixture(scope="module")
def mega() -> CompactVillage:
    return generate_mega_village(MegaConfig.from_json(ROOT / "config" / "mega.json"))


def test_water_bearing_outdoor_designs_contain_their_water():
    # S8: containment geometry exists before the source is placed.
    assert set(WATER_DESIGNS) == {"hanging_farm", "waterfall_sanctuary"}
    for outdoor_id in WATER_DESIGNS:
        assembly = generate_outdoor(outdoor_id)
        issues = validate_water_containment(assembly.scene)
        assert issues == (), (outdoor_id, issues)


def test_compact_village_water_is_contained(compact):
    assert validate_water_containment(compact.scene) == ()


def test_mega_village_water_is_contained(mega):
    assert validate_water_containment(mega.scene) == ()


def test_compact_village_has_garden_flowers(compact):
    from treehouse_village.environment import FLOWER_BLOCKS
    flowers = [position for position, block in compact.scene.blocks()
               if block.name in FLOWER_BLOCKS]
    assert len(flowers) >= 60


def test_mega_village_has_garden_flowers(mega):
    from treehouse_village.environment import FLOWER_BLOCKS
    flowers = [position for position, block in mega.scene.blocks()
               if block.name in FLOWER_BLOCKS]
    assert len(flowers) >= 200


def test_compact_village_has_lamp_posts(compact):
    from treehouse_village.environment import LAMP_FENCE, LAMP_LIGHT
    lamps = [position for position, block in compact.scene.blocks()
             if block.name == LAMP_FENCE]
    assert len(lamps) >= 15
    for position in lamps:
        light = compact.scene.get_block(position + Vec3(0, 1, 0))
        assert light is not None and light.name == LAMP_LIGHT, position


def test_mega_village_has_lamp_posts(mega):
    from treehouse_village.environment import LAMP_FENCE, LAMP_LIGHT
    lamps = [position for position, block in mega.scene.blocks()
             if block.name == LAMP_FENCE]
    assert len(lamps) >= 50
    for position in lamps:
        light = mega.scene.get_block(position + Vec3(0, 1, 0))
        assert light is not None and light.name == LAMP_LIGHT, position


def test_decor_sits_on_the_ground_plane_only(compact, mega):
    # Flowers and fence posts rest on prepared grass; the lantern rests on
    # its fence. No decor may appear inside structures (their floors are
    # not grass_block).
    from treehouse_village.environment import FLOWER_BLOCKS, LAMP_FENCE, LAMP_LIGHT
    grounded = set(FLOWER_BLOCKS) | {LAMP_FENCE}
    for village in (compact, mega):
        for position, block in village.scene.blocks():
            support = village.scene.get_block(position + Vec3(0, -1, 0))
            if block.name == LAMP_LIGHT:
                assert support is not None and support.name == LAMP_FENCE, position
            elif block.name in grounded:
                assert support is not None and support.name == "minecraft:grass_block", \
                    (position, block.name)


def test_decor_stays_clear_of_route_nodes(compact, mega):
    from treehouse_village.environment import (FLOWER_BLOCKS, LAMP_FENCE,
                                               NODE_CLEARANCE)
    decor_names = set(FLOWER_BLOCKS) | {LAMP_FENCE}
    for village in (compact, mega):
        decor_cells = {(p.x, p.y, p.z) for p, block in village.scene.blocks()
                       if block.name in decor_names}
        assert decor_cells
        for _, node in village.graph.nodes:
            for dx in range(-NODE_CLEARANCE, NODE_CLEARANCE + 1):
                for dz in range(-NODE_CLEARANCE, NODE_CLEARANCE + 1):
                    cleared = (node.x + dx, node.y, node.z + dz)
                    assert cleared not in decor_cells, (node, cleared)


def test_decor_keeps_every_route_walkable(compact, mega):
    assert validate_routes(compact.scene, compact.graph, "entrance",
                           max_climb=1) == ()
    assert validate_routes(mega.scene, mega.graph, "entrance",
                           max_climb=1) == ()
