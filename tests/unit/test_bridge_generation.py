"""T5: axis-aligned suspension bridges connecting platform anchors."""

import pytest

from treehouse_village.bridges import BridgeSpec, generate_bridge
from treehouse_village.geometry.model import Block, Scene, Vec3
from treehouse_village.validation import find_walkable_route


def _scene_with_decks(start: Vec3, end: Vec3, width: int = 5) -> Scene:
    """Anchor platforms outside the span; the bridge fills the interior gap."""
    scene = Scene()
    half = width // 2
    for dx in range(-2, 1):
        for dz in range(-half, half + 1):
            scene.set_block(start.translate(dx, 0, dz), Block("minecraft:jungle_planks"))
    for dx in range(0, 3):
        for dz in range(-half, half + 1):
            scene.set_block(end.translate(dx, 0, dz), Block("minecraft:jungle_planks"))
    return scene


def test_bridge_spec_rejects_invalid_geometry():
    with pytest.raises(ValueError):
        BridgeSpec(Vec3(0, 5, 0), Vec3(9, 5, 9))  # not axis-aligned
    with pytest.raises(ValueError):
        BridgeSpec(Vec3(0, 5, 0), Vec3(1, 5, 0))  # span too short
    with pytest.raises(ValueError):
        BridgeSpec(Vec3(0, 5, 0), Vec3(9, 5, 0), width=4)  # width must be odd
    with pytest.raises(ValueError):
        BridgeSpec(Vec3(0, 5, 0), Vec3(2, 9, 0), width=5)  # slope exceeds span
    with pytest.raises(ValueError):
        BridgeSpec(Vec3(0, 5, 0), Vec3(9, 5, 0), deck_block="jungle_planks")


def test_level_bridge_deck_is_continuous_and_interior_only():
    start, end = Vec3(0, 5, 0), Vec3(10, 5, 0)
    assembly = generate_bridge(BridgeSpec(start, end))
    blocks = {p: b for p, b in assembly.scene.blocks()}
    # Interior cells only: the anchors themselves belong to the platforms.
    assert start not in blocks and end not in blocks
    # Continuous plank deck across the whole interior span.
    for x in range(1, 10):
        deck = blocks.get(Vec3(x, 5, 0))
        assert deck is not None and deck.name == "minecraft:jungle_planks"


def test_level_bridge_is_walkable_end_to_end():
    start, end = Vec3(0, 5, 0), Vec3(10, 5, 0)
    scene = _scene_with_decks(start, end)
    assembly = generate_bridge(BridgeSpec(start, end))
    for position, block in assembly.scene.blocks():
        scene.set_block(position, block)
    # Three-wide walkable corridor between the rails.
    for offset in (-1, 0, 1):
        route = find_walkable_route(scene, start.translate(0, 1, offset),
                                    end.translate(0, 1, offset))
        assert route is not None, f"corridor offset {offset} not traversable"


def test_level_bridge_rails_towers_cables_and_lanterns():
    start, end = Vec3(0, 5, 0), Vec3(10, 5, 0)
    scene = generate_bridge(BridgeSpec(start, end)).scene
    blocks = {p: b for p, b in scene.blocks()}
    half = 2  # width 5 -> rails on the outermost deck cells
    for x in range(1, 10):
        for side in (-half, half):
            rail = blocks.get(Vec3(x, 6, side))
            assert rail is not None, f"missing rail at x={x} side={side}"
            if x in (1, 9):
                assert rail.name == "minecraft:jungle_log"       # tower posts
            else:
                assert rail.name == "minecraft:jungle_fence"     # railings
            cable = blocks.get(Vec3(x, 7, side))
            if x in (1, 9):
                assert cable is not None and cable.name == "minecraft:jungle_log"
            else:
                assert cable is not None and cable.name == "minecraft:chain"
    # Hanging lanterns below the deck edges at a deterministic interval.
    lanterns = [p for p, b in blocks.items()
                if b.name == "minecraft:lantern"
                and dict(b.properties).get("hanging") == "true"]
    assert lanterns
    for position in lanterns:
        assert position.y == 4
        assert blocks.get(position.translate(0, 1, 0)) is not None


def test_level_bridge_headroom_stays_clear_over_the_corridor():
    start, end = Vec3(0, 5, 0), Vec3(10, 5, 0)
    scene = generate_bridge(BridgeSpec(start, end)).scene
    blocks = {p for p, _ in scene.blocks()}
    for x in range(0, 11):
        for y in (6, 7):
            for offset in (-1, 0, 1):
                assert Vec3(x, y, offset) not in blocks


def test_sloped_bridge_uses_stair_risers_and_is_climbable():
    start, end = Vec3(0, 5, 0), Vec3(10, 8, 0)
    scene = _scene_with_decks(start, end)
    assembly = generate_bridge(BridgeSpec(start, end))
    blocks = {p: b for p, b in assembly.scene.blocks()}
    risers = {p for p, b in blocks.items() if b.name == "minecraft:jungle_stairs"}
    assert risers, "sloped bridge must contain stair riser blocks"
    for position in risers:
        assert dict(blocks[position].properties).get("facing") in {"north", "south",
                                                                  "east", "west"}
    for position, block in assembly.scene.blocks():
        scene.set_block(position, block)
    # The 3D route with single-block climbing crosses the slope.
    route = find_walkable_route(scene, start.translate(0, 1, 0),
                                end.translate(0, 1, 0), max_climb=1)
    assert route is not None
    # Without climbing the model honestly reports the slope as impassable.
    assert find_walkable_route(scene, start.translate(0, 1, 0),
                               end.translate(0, 1, 0)) is None


def test_bridge_anchors_are_preserved():
    start, end = Vec3(0, 5, 0), Vec3(0, 5, 10)
    scene = Scene()
    for dz in range(-2, 1):
        for dx in range(-2, 3):
            scene.set_block(start.translate(dx, 0, dz), Block("minecraft:jungle_planks"))
    for dz in range(0, 3):
        for dx in range(-2, 3):
            scene.set_block(end.translate(dx, 0, dz), Block("minecraft:jungle_planks"))
    before = {p: b for p, b in scene.blocks()}
    assembly = generate_bridge(BridgeSpec(start, end))
    # Merging the bridge must not touch or conflict with the anchor decks.
    for position, block in assembly.scene.blocks():
        scene.set_block(position, block)
    for position, block in before.items():
        assert scene.get_block(position) == block


def test_bridge_deterministic():
    spec = BridgeSpec(Vec3(0, 5, 0), Vec3(12, 6, 0))
    assert generate_bridge(spec).scene == generate_bridge(spec).scene


def test_bridge_package_exports():
    import treehouse_village.bridges as bridges
    for name in ("BridgeSpec", "BridgeAssembly", "generate_bridge"):
        assert hasattr(bridges, name)
