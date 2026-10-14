from __future__ import annotations

from dataclasses import dataclass

from ..geometry.model import Block, Scene, Vec3


@dataclass(frozen=True)
class BridgeSpec:
    """Axis-aligned suspension bridge between two platform anchor cells.

    The bridge writes only interior cells between the anchors; the anchor
    decks themselves belong to the connected platforms. Slopes are stepped
    with stair risers so the route model can cross them with single-block
    climbing.
    """

    start: Vec3
    end: Vec3
    width: int = 5
    deck_block: str = "minecraft:jungle_planks"
    rail_block: str = "minecraft:jungle_fence"
    stair_block: str = "minecraft:jungle_stairs"
    tower_block: str = "minecraft:jungle_log"
    cable_block: str = "minecraft:chain"
    lantern_block: str = "minecraft:lantern"

    def __post_init__(self) -> None:
        dx = self.end.x - self.start.x
        dz = self.end.z - self.start.z
        if (dx == 0) == (dz == 0):
            raise ValueError("bridge must be axis-aligned along exactly one horizontal axis")
        if self.width < 3 or self.width % 2 == 0:
            raise ValueError("bridge width must be an odd integer of at least 3")
        dy = abs(self.end.y - self.start.y)
        if dy * 2 > (abs(dx) or abs(dz)):
            raise ValueError("bridge slope exceeds span")
        if (abs(dx) or abs(dz)) < 3:
            raise ValueError("bridge span must be at least 3 blocks")
        for name, value in vars(self).items():
            if name.endswith("_block") and not value.startswith("minecraft:"):
                raise ValueError(f"bridge blocks must be namespaced: {name}={value!r}")


@dataclass(frozen=True)
class BridgeAssembly:
    spec: BridgeSpec
    scene: Scene


def generate_bridge(spec: BridgeSpec) -> BridgeAssembly:
    """Build one suspension bridge: deck, rails, towers, cables, lanterns."""
    scene = Scene()
    dx = spec.end.x - spec.start.x
    dz = spec.end.z - spec.start.z
    along_x = dz == 0
    span = abs(dx) if along_x else abs(dz)
    step = 1 if (dx if along_x else dz) > 0 else -1
    half = spec.width // 2
    dy_total = spec.end.y - spec.start.y

    def cell(index: int, y: int, lateral: int) -> Vec3:
        if along_x:
            return Vec3(spec.start.x + step * index, y, spec.start.z + lateral)
        return Vec3(spec.start.x + lateral, y, spec.start.z + step * index)

    def facing() -> str:
        if along_x:
            return "east" if step > 0 else "west"
        return "south" if step > 0 else "north"

    deck_y = {index: spec.start.y + (index * dy_total) // span
              for index in range(1, span)}
    risers = {index for index in range(1, span)
              if deck_y[index] > deck_y.get(index - 1, spec.start.y)}
    level_bridge = dy_total == 0

    for index in range(1, span):
        y = deck_y[index]
        for lateral in range(-half, half + 1):
            if index in risers:
                # A stair block marks the rise; a center fence column ties it
                # back to the previous deck level without blocking the rails.
                scene.set_block(cell(index, y, lateral),
                                Block(spec.stair_block, {"facing": facing(),
                                                         "half": "lower",
                                                         "shape": "straight",
                                                         "waterlogged": "false"}))
                if -half < lateral < half:
                    scene.set_block(cell(index, y - 1, lateral),
                                    Block(spec.rail_block))
            else:
                scene.set_block(cell(index, y, lateral), Block(spec.deck_block))
        for side in (-half, half):
            tower = level_bridge and index in (1, span - 1)
            rail_y = y + 1
            scene.set_block(cell(index, rail_y, side),
                            Block(spec.tower_block if tower else spec.rail_block,
                                  {"axis": "y"} if tower else ()))
            cable = cell(index, y + 2, side)
            scene.set_block(cable, Block(spec.tower_block if tower else spec.cable_block,
                                         {"axis": "y"} if tower else ()))

    # Hanging lanterns below the deck edges on a deterministic interval,
    # skipping riser cells so no support column collides with a lantern.
    lantern_index = 0
    for index in range(2, span - 1, 3):
        if index in risers:
            continue
        side = half if lantern_index % 2 == 0 else -half
        scene.set_block(cell(index, deck_y[index] - 1, side),
                        Block(spec.lantern_block, {"hanging": "true",
                                                   "waterlogged": "false"}))
        lantern_index += 1

    return BridgeAssembly(spec=spec, scene=scene)
