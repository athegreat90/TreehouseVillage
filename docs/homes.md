# Furnished residential homes

The offline generator creates four deterministic, independently composable home scenes. Each returns a sparse `Scene` and a `BuildingSpec` for fixture and coverage validation. These are residential components, **not** complete village layouts, structure NBT releases, or proof of Minecraft compatibility.

## Home catalogue

| ID | Interior footprint | Roof profile | Main palette | Covered porch |
| --- | ---: | --- | --- | ---: |
| `canopy_bungalow` | 7 × 7 | gable | jungle planks and jungle logs | 5 × 2 |
| `bamboo_veranda` | 9 × 7 | hip | bamboo planks and bamboo mosaic | 7 × 3 |
| `spruce_branch_cottage` | 7 × 9 | shed | spruce and dark-oak planks | 5 × 3 |
| `orchid_terrace_house` | 9 × 9 | terrace | acacia and dark-oak planks | 7 × 2 |

Each design has a complete plank floor, framed and glazed walls, a closed roof, an interactable two-block door, paired colored bed, barrel storage, crafting table, interior hanging lantern, porch lanterns, and a railed exterior porch. The four designs vary in footprint, material palette, porch proportions, and roof silhouette.

## Generate and validate

```python
from treehouse_village.buildings import generate_home, validate_building
from treehouse_village.geometry.model import Vec3

home = generate_home(
    "canopy_bungalow",
    seed=20261013,
    origin=Vec3(40, 80, -20),
)
assert validate_building(home.scene, home.spec) == ()
```

`HOME_DESIGNS` exposes the immutable design catalogue. `generate_home(home_id, seed=0, origin=Vec3(0, 0, 0))` returns a `HomeAssembly` containing the design, generated `Scene`, and `BuildingSpec`. The seed controls sparse roof accents; the same design, seed, and origin reproduce the same blocks. Moving the origin translates the full scene and entrance without changing local geometry.

## Coordinate and coverage rules

- The origin is the home floor level; the floor occupies relative Y=0.
- The front door is centered at relative Z=0 and faces north. The porch extends toward negative Z and leaves a clear centerline to the door.
- The wall and ceiling ring encloses the walkable room. The roof is filled upward from the ceiling deck, with profile-specific heights and no undeclared roof gaps.
- `BuildingSpec.coverage` declares `floor`, `wall`, `roof`, and `walkway` masks. Windows and both door halves occupy the wall mask; intentional openings must be omitted from a mask rather than silently treated as solid.
- Fixture requirements cover both door halves, both bed halves, each window, storage, crafting, and interior/exterior lighting, including required block states.

Coverage validation checks that declared cells contain non-air blocks. It does not validate every palette material, Minecraft registry/property legality, collision shapes, load-bearing physics, or functional gameplay; tests separately assert the intended house materials and critical states.

## Support-checker limitation

The current generic `validate_supports` helper checks only for a block directly below each position. It therefore reports warnings for interior cells of the horizontal ceiling span and for the hanging lantern, even though these components use a different support topology. Home tests separately verify that every ceiling cell is face-connected to perimeter cells supported by the wall ring and that the lantern has an overhead anchor. Do not report the generic helper as clean: it still emits these known vertical-only warnings and does not model horizontal spans or hanging attachments.

This static topology evidence is not an in-game block-update or visual test. Exact-version registry checks and Minecraft placement/gameplay validation remain outstanding.

## Checks and scope

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_home_generation.py -q
.venv\Scripts\python.exe -m pytest -q --basetemp build/pytest-t4b-final-full
```

Latest observed results: **22 focused home/API/material/support tests passed** and **125 tests passed** in the full offline suite. No Minecraft server/client home placement test was run. These scenes have not yet been connected to the Mega or Compact village layouts, bridges, production placement functions, or version-specific structure NBT artifacts.
