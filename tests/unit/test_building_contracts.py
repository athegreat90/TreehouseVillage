from __future__ import annotations

from dataclasses import replace

import pytest

from treehouse_village.buildings.contracts import (
    BuildingSpec,
    FixtureRequirement,
    validate_building,
)
from treehouse_village.geometry.model import AABB, Block, Scene, Vec3


def _spec() -> BuildingSpec:
    return BuildingSpec(
        identifier="home_a",
        category="residential",
        footprint=AABB(Vec3(0, 0, 0), Vec3(4, 3, 4)),
        entrance=Vec3(2, 1, 0),
        fixtures=(FixtureRequirement("bed", Vec3(1, 1, 1), "minecraft:white_bed"),),
    )


def test_complete_building_contract_passes():
    scene = Scene()
    scene.set_block(Vec3(2, 1, 0), Block("minecraft:oak_door"))
    scene.set_block(Vec3(1, 1, 1), Block("minecraft:white_bed"))
    assert validate_building(scene, _spec()) == ()


def test_missing_entrance_and_fixture_are_reported():
    issues = validate_building(Scene(), _spec())
    assert [issue.code for issue in issues] == ["missing_entrance", "missing_fixture"]
    assert {issue.requirement for issue in issues} == {"entrance", "bed"}


def test_building_rejects_out_of_footprint_fixture():
    spec = BuildingSpec(
        "library", "civic", AABB(Vec3(0, 0, 0), Vec3(2, 2, 2)), Vec3(1, 1, 0),
        (FixtureRequirement("lectern", Vec3(5, 1, 1), "minecraft:lectern"),),
    )
    scene = Scene()
    scene.set_block(spec.entrance, Block("minecraft:oak_door"))
    issues = validate_building(scene, spec)
    assert [(issue.code, issue.requirement) for issue in issues] == [
        ("fixture_outside_footprint", "lectern"),
    ]


def test_building_specs_require_namespaced_fixture_blocks():
    try:
        FixtureRequirement("bad", Vec3(0, 0, 0), "stone")
    except ValueError as error:
        assert "namespaced" in str(error)
    else:
        raise AssertionError("expected namespaced block validation")


@pytest.mark.parametrize("surface", ["floor", "wall", "roof", "walkway"])
def test_coverage_detects_missing_and_air_blocks_without_mutating_scene(surface):
    from treehouse_village.buildings.contracts import CoverageRequirement

    position = Vec3(1, 0, 1)
    spec = replace(_spec(), fixtures=(), coverage=(CoverageRequirement(surface, (position,)),))
    for block in (None, Block("minecraft:air"), Block("minecraft:cave_air"),
                  Block("minecraft:void_air")):
        blocks = {spec.entrance: Block("minecraft:oak_door")}
        if block is not None:
            blocks[position] = block
        scene = Scene(blocks)
        before = scene.blocks()
        issues = validate_building(scene, spec)
        assert [(issue.code, issue.requirement, issue.position) for issue in issues] == [
            ("missing_coverage", surface, position),
        ]
        assert scene.blocks() == before


def test_complete_coverage_allows_an_intentional_opening():
    from treehouse_village.buildings.contracts import CoverageRequirement

    positions = (Vec3(0, 0, 0), Vec3(2, 0, 0))
    spec = replace(_spec(), fixtures=(), coverage=(CoverageRequirement("floor", positions),))
    scene = Scene({position: Block("minecraft:jungle_planks") for position in positions})
    scene.set_block(spec.entrance, Block("minecraft:oak_door"))
    assert scene.get_block(Vec3(1, 0, 0)) is None
    assert validate_building(scene, spec) == ()


def test_coverage_reports_outside_footprint_even_when_block_exists():
    from treehouse_village.buildings.contracts import CoverageRequirement

    position = Vec3(9, 0, 0)
    spec = replace(_spec(), fixtures=(), coverage=(CoverageRequirement("roof", (position,)),))
    scene = Scene({position: Block("minecraft:jungle_planks"),
                   spec.entrance: Block("minecraft:oak_door")})
    assert [(issue.code, issue.requirement) for issue in validate_building(scene, spec)] == [
        ("coverage_outside_footprint", "roof"),
    ]


def test_fixture_required_states_detect_wrong_bed_half_and_preserve_previous_behavior():
    position = Vec3(1, 1, 1)
    fixture = FixtureRequirement("bed", position, "minecraft:white_bed",
                                 required_properties={"part": "foot", "facing": "east"})
    spec = replace(_spec(), fixtures=(fixture,))
    for properties, expected in [
        ({"part": "head", "facing": "east"}, ["fixture_state_mismatch"]),
        ({"part": "foot"}, ["fixture_state_mismatch"]),
        ({"part": "foot", "facing": "east", "occupied": "false"}, []),
    ]:
        scene = Scene({position: Block("minecraft:white_bed", properties),
                       spec.entrance: Block("minecraft:oak_door")})
        assert [issue.code for issue in validate_building(scene, spec)] == expected
    # Existing contracts without explicit states retain their original semantics.
    scene = Scene({position: Block("minecraft:white_bed"),
                   spec.entrance: Block("minecraft:oak_door")})
    assert validate_building(scene, _spec()) == ()


def test_entrance_outside_footprint_does_not_cascade_or_mutate_scene():
    spec = replace(_spec(), entrance=Vec3(9, 1, 0), fixtures=())
    scene = Scene()
    before = scene.blocks()
    assert [issue.code for issue in validate_building(scene, spec)] == [
        "entrance_outside_footprint",
    ]
    assert scene.blocks() == before


def test_duplicate_coverage_positions_produce_one_issue():
    from treehouse_village.buildings.contracts import CoverageRequirement

    position = Vec3(1, 0, 1)
    spec = replace(_spec(), fixtures=(),
                   coverage=(CoverageRequirement("floor", (position, position)),))
    scene = Scene({spec.entrance: Block("minecraft:oak_door")})
    assert [(issue.code, issue.position) for issue in validate_building(scene, spec)] == [
        ("missing_coverage", position),
    ]


@pytest.mark.parametrize("surface", ["floor", "wall", "roof", "walkway"])
@pytest.mark.parametrize("name", ["minecraft:water", "minecraft:oak_leaves"])
def test_coverage_is_occupancy_only_not_material_validation(surface, name):
    from treehouse_village.buildings.contracts import CoverageRequirement

    position = Vec3(1, 0, 1)
    spec = replace(_spec(), fixtures=(), coverage=(CoverageRequirement(surface, (position,)),))
    scene = Scene({spec.entrance: Block("minecraft:oak_door"), position: Block(name)})
    assert validate_building(scene, spec) == ()
