"""T9: static water containment validation (S8).

"S8: Build all containment and support geometry before placing water
sources." Offline we cannot tick fluids, so the durable contract is
geometric: every `minecraft:water` cell must sit on a supporting block
(or the prepared site plane) and be closed on all four horizontal sides,
so loading the template cannot make it spread or drip.
"""

from treehouse_village.geometry.model import Block, Scene, Vec3
from treehouse_village.validation import validate_water_containment


def _floor(scene: Scene, *, skip: tuple[tuple[int, int], ...] = ()) -> None:
    skip_set = set(skip)
    for x in range(3):
        for z in range(3):
            if (x, z) in skip_set:
                continue
            scene.set_block(Vec3(x, 0, z), Block("minecraft:mossy_cobblestone"))


def test_enclosed_floor_level_water_is_contained():
    # Water embedded in the floor: below is the prepared site (ground_y=0),
    # the four sides are floor blocks — nothing to spread into.
    scene = Scene()
    _floor(scene, skip=((1, 1),))
    scene.set_block(Vec3(1, 0, 1), Block("minecraft:water"))
    assert validate_water_containment(scene) == ()


def test_water_with_an_open_horizontal_side_is_reported():
    scene = Scene()
    # The water cell and one of its horizontal neighbours are left open.
    _floor(scene, skip=((1, 1), (2, 1)))
    scene.set_block(Vec3(1, 0, 1), Block("minecraft:water"))
    issues = validate_water_containment(scene)
    assert [(issue.code, issue.position) for issue in issues] == [
        ("water_uncontained", Vec3(1, 0, 1)),
    ]


def test_water_without_support_below_is_reported():
    scene = Scene()
    scene.set_block(Vec3(1, 1, 1), Block("minecraft:water"))
    issues = validate_water_containment(scene)
    assert [(issue.code, issue.position) for issue in issues] == [
        ("water_unsupported", Vec3(1, 1, 1)),
    ]


def test_every_level_of_an_open_water_column_needs_enclosure():
    scene = Scene()
    _floor(scene)
    scene.set_block(Vec3(1, 1, 1), Block("minecraft:water"))
    scene.set_block(Vec3(1, 2, 1), Block("minecraft:water"))
    issues = validate_water_containment(scene)
    assert [(issue.code, issue.position) for issue in issues] == [
        ("water_uncontained", Vec3(1, 1, 1)),
        ("water_uncontained", Vec3(1, 2, 1)),
    ]


def test_enclosed_water_column_passes():
    scene = Scene()
    _floor(scene)
    scene.set_block(Vec3(1, 1, 1), Block("minecraft:water"))
    scene.set_block(Vec3(1, 2, 1), Block("minecraft:water"))
    # Guide the chute on all four sides at both levels.
    for y in (1, 2):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            scene.set_block(Vec3(1 + dx, y, 1 + dz), Block("minecraft:mossy_cobblestone"))
    assert validate_water_containment(scene) == ()


def test_support_check_uses_an_explicit_ground_plane():
    # A caller with a different prepared terrain plane passes ground_y; the
    # water sits ON that plane, fully enclosed by the plane's own blocks.
    scene = Scene()
    for x in range(3):
        for z in range(3):
            if (x, z) != (1, 1):
                scene.set_block(Vec3(x, 5, z), Block("minecraft:mossy_cobblestone"))
    scene.set_block(Vec3(1, 5, 1), Block("minecraft:water"))
    assert validate_water_containment(scene, ground_y=5) == ()

    strict = validate_water_containment(scene, ground_y=0)
    assert [(issue.code, issue.position) for issue in strict] == [
        ("water_unsupported", Vec3(1, 5, 1)),
    ]
