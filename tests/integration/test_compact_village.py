"""T6: complete Compact village — independent composition, routes, reconstruction."""

from pathlib import Path

import pytest

from treehouse_village.buildings import validate_building
from treehouse_village.config import CompactConfig
from treehouse_village.geometry.model import Vec3
from treehouse_village.routes import validate_routes
from treehouse_village.serialization import (StructureSerializer,
                                             reconstruct_segments,
                                             segment_scene)
from treehouse_village.village import CompactVillage, generate_compact_village

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "compact.json"


@pytest.fixture(scope="module")
def config() -> CompactConfig:
    return CompactConfig.from_json(CONFIG_PATH)


@pytest.fixture(scope="module")
def village(config) -> CompactVillage:
    return generate_compact_village(config)


def test_compact_config_loads(config):
    assert config.variant == "compact"
    assert config.width == 96 and config.depth == 96
    assert len(config.trees) == 5


def test_compact_counts(village):
    assert len(village.trees) == 5
    assert len(village.buildings) >= 6
    assert len(village.bridges) >= 7


def test_compact_footprint_fits(village):
    bounds = village.scene.bounds  # property, not a method
    assert bounds is not None
    assert 0 <= bounds.minimum.x and bounds.maximum.x <= 95
    assert 0 <= bounds.minimum.z and bounds.maximum.z <= 95


def test_every_building_contract_valid_in_village(village):
    for spec in village.buildings:
        assert validate_building(village.scene, spec) == (), spec.identifier


def test_route_graph_reaches_every_destination(village):
    assert validate_routes(village.scene, village.graph, "entrance",
                           max_climb=1) == ()


def test_route_graph_covers_mandatory_destinations(village):
    names = {name for name, _ in village.graph.nodes}
    assert {"entrance", "balcony", "market", "farm", "observatory",
            "sanctuary", "home_north", "home_south"} <= names
    assert len([n for n in names if n.startswith("tree_")]) == 5


def test_ground_plane_is_a_prepared_site(village):
    # Grass fills unused cells; structures keep their own floors and trunks.
    assert village.scene.get_block(Vec3(35, 0, 30)).name == "minecraft:grass_block"
    assert village.scene.get_block(Vec3(21, 0, 56)).name == "minecraft:jungle_planks"
    assert village.scene.get_block(Vec3(47, 0, 47)).name == "minecraft:stripped_jungle_log"


def test_tree_platforms_present(village):
    for tree in village.config.trees:
        edge = village.scene.get_block(Vec3(tree.x + 4, tree.platform_level, tree.z))
        assert edge is not None and edge.name == "minecraft:jungle_planks"
        trunk = village.scene.get_block(Vec3(tree.x, 5, tree.z))
        assert trunk is not None and trunk.name == "minecraft:jungle_log"


def test_deterministic(config):
    first = generate_compact_village(config)
    second = generate_compact_village(config)
    assert first.scene == second.scene


def test_segmentation_reconstructs_village(village):
    segments = segment_scene(village.scene, max_size=Vec3(48, 32, 48))
    assert len(segments) == 4
    assert reconstruct_segments(segments) == village.scene
    serializer = StructureSerializer(data_version=5023)
    for segment in segments:
        data = serializer.dumps(segment.scene)
        assert data[:2] == b"\x1f\x8b"  # gzip magic: real compressed NBT
