from __future__ import annotations

from dataclasses import dataclass

from ..geometry.model import Scene, Vec3


@dataclass(frozen=True)
class Segment:
    origin: Vec3
    scene: Scene


def segment_scene(scene: Scene, *, max_size: Vec3) -> tuple[Segment, ...]:
    if any(value <= 0 for value in (max_size.x, max_size.y, max_size.z)):
        raise ValueError("max_size components must be positive")
    bounds = scene.bounds
    if bounds is None:
        return ()
    groups: dict[Vec3, Scene] = {}
    for position, block in scene.blocks():
        origin = Vec3(
            (position.x // max_size.x) * max_size.x,
            (position.y // max_size.y) * max_size.y,
            (position.z // max_size.z) * max_size.z,
        )
        groups.setdefault(origin, Scene()).set_block(position - origin, block)
    return tuple(Segment(origin, groups[origin]) for origin in sorted(groups))


def reconstruct_segments(segments: tuple[Segment, ...] | list[Segment]) -> Scene:
    scene = Scene()
    for segment in segments:
        for position, block in segment.scene.blocks():
            scene.set_block(position + segment.origin, block)
    return scene
