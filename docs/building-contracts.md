# Validate building coverage and fixtures

Building contracts compare explicit architectural requirements with a generated
`Scene`. They are an offline foundation, not proof of a complete village or
Minecraft compatibility.

## Quick path

```python
from treehouse_village.buildings import (
    BuildingSpec, CoverageRequirement, FixtureRequirement, validate_building,
)
from treehouse_village.geometry.model import AABB, Vec3

spec = BuildingSpec(
    identifier="home_a",
    category="residential",
    footprint=AABB(Vec3(0, 0, 0), Vec3(8, 6, 8)),
    entrance=Vec3(4, 1, 0),
    fixtures=(FixtureRequirement(
        "bed_foot", Vec3(2, 1, 2), "minecraft:white_bed",
        required_properties={"part": "foot", "facing": "east"},
    ),),
    coverage=(CoverageRequirement("floor", (Vec3(2, 0, 2),)),),
)
# Supply the actual generated scene; this example declares a partial contract.
# issues = validate_building(scene, spec)
```

## Contract behavior

| Requirement | Check |
| --- | --- |
| Entrance | Must lie inside the footprint and have a block |
| Fixture | Must lie inside the footprint and match the required block name |
| Required properties | Every declared property must match; other properties are allowed |
| Coverage | Every declared cell must lie inside the footprint and contain a non-air block |
| Intentional openings | Exclude them from the corresponding coverage mask |

Coverage cells are deduplicated and sorted. Validation reports all applicable
issues without modifying the scene. Existing fixture contracts without required
properties retain their name-only behavior.

Use separate `floor`, `wall`, `roof` and `walkway` masks. Store expected masks
independently of generated block occupancy so generator omissions remain visible.
A water block or decorative plant is non-air: coverage alone does **not** prove
that a cell has the correct structural material, collision shape or support.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_building_contracts.py -q
.venv\Scripts\python.exe -m pytest -q --basetemp build/pytest-t4a
```

Tests exercise missing/air coverage for all four surface types, intentional
openings, out-of-footprint coverage, required bed states, previous name-only
fixture behavior, and non-mutating validation.

## Remaining gates

Complete building generators must declare both bed halves, door halves, supports,
full coverage and furnishings. Exact-version registry/state validation, supported
materials, collision-aware entrances, enchanting mechanics, 3D traversal and
in-game verification remain separate requirements. This module checks declared
properties; it does not discover whether a property is legal in Minecraft.
