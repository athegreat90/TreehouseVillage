from __future__ import annotations

from dataclasses import dataclass
import math
import random

from ..geometry.model import AABB, Block, Scene, Vec3


@dataclass(frozen=True)
class TreeSpec:
    origin: Vec3
    height: int
    seed: int
    platform_level: int | None = None
    platform_radius: int = 4

    def __post_init__(self) -> None:
        if self.height < 8:
            raise ValueError("tree height must be at least 8")
        level = self.platform_level if self.platform_level is not None else self.height // 2
        if not 3 <= level < self.height - 2:
            raise ValueError("platform_level must be inside the trunk")
        if self.platform_radius < 2:
            raise ValueError("platform_radius must be at least 2")
        object.__setattr__(self, "platform_level", level)


@dataclass(frozen=True)
class TreeAssembly:
    scene: Scene
    clearance: AABB
    platform_level: int


def generate_tree(spec: TreeSpec) -> TreeAssembly:
    rng = random.Random(spec.seed)
    scene = Scene()
    origin = spec.origin
    level = spec.platform_level
    assert level is not None

    def put(position: Vec3, name: str) -> None:
        # Organic components may converge at a trunk/branch join. Preserve
        # the first structural block instead of overwriting it with decor.
        if scene.get_block(position) is not None:
            return
        scene.set_block(position, Block(name))

    def put_log(position: Vec3, axis: str = "y") -> None:
        existing = scene.get_block(position)
        if existing is not None:
            # Branch/root overlaps are intentional organic joins. Keep the
            # first deterministic state rather than treating the join as a
            # destructive scene conflict.
            if existing.name == "minecraft:jungle_log":
                return
            raise ValueError(f"tree component collides at {position}: {existing.name}")
        scene.set_block(position, Block("minecraft:jungle_log", {"axis": axis}))

    # Tapered, slightly wandering trunk with deterministic irregular radii.
    drift_x = 0
    drift_z = 0
    for y in range(spec.height):
        if y and y % 4 == 0:
            drift_x += rng.choice((-1, 0, 0, 1))
            drift_z += rng.choice((-1, 0, 0, 1))
        radius = 2 if y < spec.height // 3 else 1
        if y > spec.height * 0.8:
            radius = 1
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if dx * dx + dz * dz <= radius * radius + 1:
                    put_log(origin.translate(drift_x + dx, y, drift_z + dz))

    # Roots radiate into the ground plane.
    for index in range(8):
        angle = index * math.tau / 8 + rng.uniform(-0.12, 0.12)
        length = rng.randint(3, 6)
        for step in range(1, length + 1):
            x = round(math.cos(angle) * step)
            z = round(math.sin(angle) * step)
            put_log(origin.translate(x, 0, z), "x" if abs(x) >= abs(z) else "z")

    # Primary and secondary branches are voxel lines attached to the trunk.
    for index, branch_y in enumerate((spec.height // 3, spec.height // 2, spec.height * 2 // 3)):
        for branch in range(4):
            angle = branch * math.tau / 4 + index * 0.37 + rng.uniform(-0.15, 0.15)
            length = 4 + rng.randint(0, 3)
            for step in range(1, length + 1):
                x = round(math.cos(angle) * step)
                z = round(math.sin(angle) * step)
                y = branch_y + step // 3
                put_log(origin.translate(x, y, z), "x" if abs(x) >= abs(z) else "z")
            tip = origin.translate(round(math.cos(angle) * length), branch_y + length // 3,
                                   round(math.sin(angle) * length))
            for secondary in (-1, 1):
                sub_angle = angle + secondary * 0.55
                for step in range(1, 3):
                    put_log(tip.translate(round(math.cos(sub_angle) * step), step // 2,
                                          round(math.sin(sub_angle) * step)),
                            "x" if abs(math.cos(sub_angle)) >= abs(math.sin(sub_angle)) else "z")

    # Circular platform and four underside supports. The central trunk remains.
    radius = spec.platform_radius
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            if dx * dx + dz * dz <= radius * radius:
                put(origin.translate(dx, level, dz), "minecraft:jungle_planks")
    for dx, dz in ((radius - 1, 0), (-(radius - 1), 0), (0, radius - 1), (0, -(radius - 1))):
        put_log(origin.translate(dx, level - 1, dz))

    # Canopy clusters stay above the platform and outside reserved player clearance.
    for cluster in range(7):
        angle = cluster * math.tau / 7 + rng.uniform(-0.2, 0.2)
        distance = rng.randint(3, 7)
        center = origin.translate(round(math.cos(angle) * distance),
                                  rng.randint(level + 3, spec.height - 1),
                                  round(math.sin(angle) * distance))
        for dx in range(-2, 3):
            for dy in range(-1, 2):
                for dz in range(-2, 3):
                    if dx * dx + dz * dz + dy * dy <= 7:
                        position = center.translate(dx, dy, dz)
                        if not (abs(position.x - origin.x) <= 2 and
                                abs(position.z - origin.z) <= 2 and
                                origin.y <= position.y <= origin.y + level + 2):
                            put(position, "minecraft:jungle_leaves")

    # Clearance reserves the climb corridor up to the platform underside;
    # the platform itself is an intentional occupied destination volume.
    clearance = AABB(origin.translate(-2, 0, -2),
                     origin.translate(2, level - 1, 2))
    return TreeAssembly(scene, clearance, level)
