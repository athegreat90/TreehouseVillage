from __future__ import annotations

from collections import deque

import pytest

from treehouse_village.buildings import (
    BuildingIssue,
    BuildingSpec,
    CoverageRequirement,
    FixtureRequirement,
    HOME_DESIGNS,
    HomeAssembly,
    HomeDesign,
    generate_home,
    validate_building,
)
from treehouse_village.geometry.model import Vec3
from treehouse_village.validation.structural import validate_supports


def test_buildings_package_preserves_contract_exports_and_exposes_home_api():
    assert all((
        BuildingIssue,
        BuildingSpec,
        CoverageRequirement,
        FixtureRequirement,
        HomeAssembly,
        HomeDesign,
        generate_home,
        validate_building,
    ))
    assert len(HOME_DESIGNS) == 4


MANDATORY_FIXTURES = {
    "front_door_lower",
    "front_door_upper",
    "bed_foot",
    "bed_head",
    "storage",
    "crafting_table",
    "interior_light",
    "exterior_light",
}


@pytest.mark.parametrize("home_id", tuple(HOME_DESIGNS))
def test_each_furnished_home_satisfies_its_complete_building_contract(home_id):
    origin = Vec3(11, 42, -7)
    assembly = generate_home(home_id, seed=20261013, origin=origin)
    design = HOME_DESIGNS[home_id]

    assert validate_building(assembly.scene, assembly.spec) == ()
    coverage = {requirement.name: requirement.positions
                for requirement in assembly.spec.coverage}
    assert set(coverage) == {"floor", "wall", "roof", "walkway"}
    assert len(coverage["floor"]) == design.width * design.depth
    assert len(coverage["wall"]) >= 2 * (design.width + design.depth - 2)
    assert coverage["roof"]
    assert len(coverage["walkway"]) == design.porch_width * design.porch_depth
    assert all(assembly.scene.get_block(position).name == design.floor_block
               for position in coverage["floor"])
    assert all(assembly.scene.get_block(position).name == design.floor_block
               for position in coverage["walkway"])
    wall_materials = {design.wall_block, design.frame_block, design.door_block,
                      design.window_block}
    assert all(assembly.scene.get_block(position).name in wall_materials
               for position in coverage["wall"])
    roof_materials = {design.roof_block, design.accent_block, "minecraft:lantern"}
    assert all(assembly.scene.get_block(position).name in roof_materials
               for position in coverage["roof"])

    fixtures = {fixture.name: fixture for fixture in assembly.spec.fixtures}
    assert MANDATORY_FIXTURES <= fixtures.keys()
    for name in MANDATORY_FIXTURES:
        fixture = fixtures[name]
        block = assembly.scene.get_block(fixture.position)
        assert block is not None
        assert block.name == fixture.block_name
        assert all(dict(block.properties).get(key) == value
                   for key, value in fixture.required_properties)

    assert assembly.spec.footprint.contains(assembly.spec.entrance)
    assert assembly.scene.bounds is not None
    assert all(assembly.spec.footprint.contains(position)
               for position, _ in assembly.scene.blocks())


@pytest.mark.parametrize("home_id", tuple(HOME_DESIGNS))
def test_home_roof_is_fully_occupied_and_each_roof_voxel_is_supported(home_id):
    assembly = generate_home(home_id, seed=17)
    roof = next(requirement for requirement in assembly.spec.coverage
                if requirement.name == "roof")

    for position in roof.positions:
        block = assembly.scene.get_block(position)
        assert block is not None
        if position.y > 3:
            assert assembly.scene.get_block(position.translate(0, -1, 0)) is not None


@pytest.mark.parametrize("home_id", tuple(HOME_DESIGNS))
def test_ceiling_span_is_connected_to_supported_walls_and_lantern_is_anchored(home_id):
    design = HOME_DESIGNS[home_id]
    assembly = generate_home(home_id, seed=29)
    roof = next(requirement for requirement in assembly.spec.coverage
                if requirement.name == "roof")
    ceiling = {position for position in roof.positions if position.y == 3}
    expected = {Vec3(x, 3, z) for x in range(design.width) for z in range(design.depth)}
    assert ceiling == expected

    perimeter = {position for position in ceiling
                 if position.x in (0, design.width - 1) or
                 position.z in (0, design.depth - 1)}
    assert all(assembly.scene.get_block(position.translate(0, -1, 0)) is not None
               for position in perimeter)
    reached = set(perimeter)
    queue = deque(perimeter)
    while queue:
        current = queue.popleft()
        for neighbor in (current.translate(1, 0, 0), current.translate(-1, 0, 0),
                         current.translate(0, 0, 1), current.translate(0, 0, -1)):
            if neighbor in ceiling and neighbor not in reached:
                reached.add(neighbor)
                queue.append(neighbor)
    assert reached == ceiling

    light = next(fixture for fixture in assembly.spec.fixtures
                 if fixture.name == "interior_light")
    assert dict(assembly.scene.get_block(light.position).properties)["hanging"] == "true"
    assert assembly.scene.get_block(light.position.translate(0, 1, 0)) is not None

    expected_span_warnings = {
        Vec3(x, 3, z)
        for x in range(1, design.width - 1)
        for z in range(1, design.depth - 1)
    }
    assert {issue.position for issue in validate_supports(assembly.scene)} <= expected_span_warnings


@pytest.mark.parametrize("home_id", tuple(HOME_DESIGNS))
def test_balcony_path_is_continuous_clear_and_reaches_the_door(home_id):
    design = HOME_DESIGNS[home_id]
    assembly = generate_home(home_id, seed=23)
    center_x = design.width // 2
    walkway = next(requirement for requirement in assembly.spec.coverage
                   if requirement.name == "walkway")
    walkway_cells = set(walkway.positions)

    for z in range(-design.porch_depth, 0):
        assert Vec3(center_x, 0, z) in walkway_cells
        assert assembly.scene.get_block(Vec3(center_x, 1, z)) is None
        assert assembly.scene.get_block(Vec3(center_x, 2, z)) is None
    assert assembly.spec.entrance == Vec3(center_x, 1, 0)
    assert assembly.scene.get_block(assembly.spec.entrance).name.endswith("_door")


@pytest.mark.parametrize("home_id", tuple(HOME_DESIGNS))
def test_home_generation_is_deterministic_and_origin_relative(home_id):
    seed = 9981
    origin = Vec3(-24, 70, 31)
    offset = Vec3(13, 5, -9)
    first = generate_home(home_id, seed=seed, origin=origin)
    repeated = generate_home(home_id, seed=seed, origin=origin)
    moved = generate_home(home_id, seed=seed, origin=origin + offset)

    assert first.scene == repeated.scene
    assert moved.scene == first.scene.translated(offset)
    assert moved.spec.entrance == first.spec.entrance + offset


def test_four_home_designs_have_distinct_palettes_and_roof_profiles():
    designs = tuple(HOME_DESIGNS.values())

    assert len(designs) == 4
    assert len({design.identifier for design in designs}) == 4
    assert len({design.floor_block for design in designs}) == 4
    assert len({design.roof_style for design in designs}) == 4
    scenes = [generate_home(design.identifier, seed=5).scene for design in designs]
    assert all(left != right for index, left in enumerate(scenes)
               for right in scenes[index + 1:])
