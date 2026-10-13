from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from ..geometry.model import AABB, Scene, Vec3


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    position: Vec3
    message: str


def validate_supports(scene: Scene, *, ground_y: int | None = None,
                      unsupported_names: frozenset[str] = frozenset()) -> tuple[ValidationIssue, ...]:
    """Report blocks with no directly supporting block below them."""
    if not scene:
        return ()
    # The default build plane is world Y=0; callers with another prepared
    # terrain plane must provide ground_y explicitly.
    minimum_y = ground_y if ground_y is not None else 0
    issues: list[ValidationIssue] = []
    for position, block in scene.blocks():
        if position.y <= minimum_y or block.name in unsupported_names:
            continue
        if scene.get_block(position.translate(0, -1, 0)) is None:
            issues.append(ValidationIssue(
                "unsupported_block", position,
                f"{block.name} has no supporting block below it",
            ))
    return tuple(issues)


def validate_reserved_volumes(scene: Scene, volumes: Iterable[AABB]) -> tuple[ValidationIssue, ...]:
    reserved = tuple(volumes)
    return tuple(
        ValidationIssue("reserved_collision", position,
                        f"{block.name} occupies a reserved empty volume")
        for position, block in scene.blocks()
        if any(volume.contains(position) for volume in reserved)
    )


def find_walkable_route(scene: Scene, start: Vec3, goal: Vec3) -> tuple[Vec3, ...] | None:
    """Find a four-direction route through empty blocks with support and headroom."""
    if not _walkable(scene, start) or not _walkable(scene, goal):
        return None
    queue: deque[Vec3] = deque([start])
    previous: dict[Vec3, Vec3 | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path: list[Vec3] = []
            while current is not None:
                path.append(current)
                current = previous[current]
            return tuple(reversed(path))
        for offset in (Vec3(1, 0, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1), Vec3(0, 0, -1)):
            candidate = current + offset
            if candidate not in previous and _walkable(scene, candidate):
                previous[candidate] = current
                queue.append(candidate)
    return None


def _walkable(scene: Scene, position: Vec3) -> bool:
    return (scene.get_block(position) is None and
            scene.get_block(position.translate(0, -1, 0)) is not None and
            scene.get_block(position.translate(0, 1, 0)) is None)
