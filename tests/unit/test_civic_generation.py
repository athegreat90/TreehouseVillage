import pytest

from treehouse_village.buildings import CIVIC_DESIGNS, generate_civic, validate_building
from treehouse_village.geometry.model import Block


def test_all_civic_designs_generate_valid_contracts():
    for civic_id in CIVIC_DESIGNS:
        assembly = generate_civic(civic_id)
        assert validate_building(assembly.scene, assembly.spec) == ()


def test_civic_fixtures_are_nonempty_and_inbounds():
    for civic_id, design in CIVIC_DESIGNS.items():
        assembly = generate_civic(civic_id)
        assert assembly.spec.fixtures
        for fixture in assembly.spec.fixtures:
            assert assembly.spec.footprint.contains(fixture.position)
            assert assembly.scene.get_block(fixture.position).name == fixture.block_name


def test_civic_coverage_is_complete():
    for civic_id in CIVIC_DESIGNS:
        assembly = generate_civic(civic_id)
        for requirement in assembly.spec.coverage:
            for position in requirement.positions:
                block = assembly.scene.get_block(position)
                assert block is not None and block.name not in {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def test_civic_generation_is_deterministic():
    first = generate_civic("library_enchanting", seed=7)
    second = generate_civic("library_enchanting", seed=7)
    assert first.scene == second.scene
    assert first.spec == second.spec


def test_civic_origin_translation():
    assembly = generate_civic("alchemy_hut", origin=__import__("treehouse_village.geometry.model", fromlist=["Vec3"]).Vec3(10, 5, 20))
    assert assembly.spec.footprint.minimum == __import__("treehouse_village.geometry.model", fromlist=["Vec3"]).Vec3(10, 5, 20)
