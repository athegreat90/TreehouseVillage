"""T7: complete Mega village — 176x176, nine giant trees, 15+ bridges."""

from pathlib import Path

import pytest

from treehouse_village.buildings import validate_building
from treehouse_village.config import MegaConfig
from treehouse_village.geometry.model import Vec3
from treehouse_village.routes import validate_routes
from treehouse_village.serialization import (StructureSerializer,
                                             reconstruct_segments,
                                             segment_scene)
from treehouse_village.village import generate_mega_village

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "mega.json"


@pytest.fixture(scope="module")
def config() -> MegaConfig:
    return MegaConfig.from_json(CONFIG_PATH)


@pytest.fixture(scope="module")
def village(config) -> object:
    return generate_mega_village(config)


def test_mega_config_loads(config):
    assert config.variant == "mega"
    assert config.width == 176 and config.depth == 176
    assert len(config.trees) == 9


def test_mega_counts(village):
    assert len(village.trees) == 9
    assert len(village.buildings) >= 12
    assert len(village.bridges) >= 15


def test_mega_footprint_fits(village):
    bounds = village.scene.bounds
    assert 0 <= bounds.minimum.x and bounds.maximum.x <= 175
    assert 0 <= bounds.minimum.z and bounds.maximum.z <= 175


def test_mega_village_height_in_spec_range(village):
    # Spec: approximately 70-85 blocks tall (ground plane starts at y=0).
    assert 70 <= village.scene.bounds.maximum.y <= 85


def test_mega_has_four_distinct_homes(village):
    homes = {spec.identifier for spec in village.buildings
             if spec.category == "residential"}
    assert len(homes) == 4


def test_mega_has_two_waterfall_sanctuaries(village):
    sanctuaries = [spec for spec in village.buildings
                   if spec.identifier == "waterfall_sanctuary"]
    assert len(sanctuaries) == 2
    for spec in sanctuaries:
        assert any(fixture.block_name == "minecraft:water"
                   for fixture in spec.fixtures)


def test_mega_has_three_viewing_platforms(village):
    identifiers = {spec.identifier for spec in village.buildings}
    assert {"sunset_observatory", "watchtower", "village_hall"} <= identifiers
    hall = next(spec for spec in village.buildings
                if spec.identifier == "village_hall")
    platform = next(c for c in hall.coverage if c.name == "platform")
    assert len(platform.positions) > 0


def test_every_building_contract_valid_in_mega(village):
    for spec in village.buildings:
        assert validate_building(village.scene, spec) == (), spec.identifier


def test_mega_route_graph_reaches_every_destination(village):
    assert validate_routes(village.scene, village.graph, "entrance",
                           max_climb=1) == ()


def test_mega_route_graph_covers_mandatory_destinations(village):
    names = {name for name, _ in village.graph.nodes}
    assert {"entrance", "balcony", "market", "farm", "observatory",
            "sanctuary_north", "sanctuary_south", "home_north",
            "home_east", "home_southwest", "home_southeast",
            "library", "workshop", "warehouse", "alchemy",
            "watchtower"} <= names
    assert len([n for n in names if n.startswith("tree_")]) == 9


def test_mega_ground_plane_is_prepared_site(village):
    assert village.scene.get_block(Vec3(10, 0, 10)).name == "minecraft:grass_block"
    assert village.scene.get_block(Vec3(47, 0, 87)).name == "minecraft:stripped_jungle_log"
    assert village.scene.get_block(Vec3(110, 0, 10)).name == "minecraft:grass_block"


def test_mega_tree_platforms_present(village):
    for tree in village.config.trees:
        # dx=5, not T6's dx=4: mega trunks use radius 2 below height//3
        # (~25), so with drift (+/-2 by y=10) trunk logs reach dx=4 but
        # never dx=5 (needs 3+ inside a radius-2 disc of the drifted axis).
        edge = village.scene.get_block(
            Vec3(tree.x + 5, tree.platform_level, tree.z))
        assert edge is not None and edge.name == "minecraft:jungle_planks"
        trunk = village.scene.get_block(Vec3(tree.x, 5, tree.z))
        assert trunk is not None and trunk.name == "minecraft:jungle_log"


def test_mega_deterministic(config):
    first = generate_mega_village(config)
    second = generate_mega_village(config)
    assert first.scene == second.scene


def test_mega_segmentation_reconstructs_village(village):
    segments = segment_scene(village.scene, max_size=Vec3(48, 32, 48))
    assert len(segments) > 1
    assert reconstruct_segments(segments) == village.scene
    serializer = StructureSerializer(data_version=5023)
    for segment in segments:
        data = serializer.dumps(segment.scene)
        assert data[:2] == b"\x1f\x8b"  # gzip magic: real compressed NBT
