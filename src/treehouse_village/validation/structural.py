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


def is_walkable(scene: Scene, position: Vec3) -> bool:
    """Public predicate for a walkable standing cell."""
    return _walkable(scene, position)


def find_walkable_route(scene: Scene, start: Vec3, goal: Vec3, *,
                        max_climb: int = 0,
                        max_drop: int = 0) -> tuple[Vec3, ...] | None:
    """Find a four-direction route through empty blocks with support and headroom.

    ``max_climb`` allows stepping onto a neighbor column whose top supports a
    standing cell up to that many blocks above the current one (stair risers,
    single-block jumps). ``max_drop`` allows safely dropping down onto a
    walkable cell through open air by the same amount. Both default to zero,
    preserving plain horizontal traversal.
    """
    if max_climb < 0 or max_drop < 0:
        raise ValueError("max_climb and max_drop must be non-negative")
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
            for neighbor in _neighbors(scene, current, candidate,
                                       max_climb, max_drop):
                if neighbor not in previous:
                    previous[neighbor] = current
                    queue.append(neighbor)
    return None


def _neighbors(scene: Scene, current: Vec3, candidate: Vec3,
               max_climb: int, max_drop: int):
    if _walkable(scene, candidate):
        yield candidate
        return
    # Climb: the candidate column must be solid for the stepped height and
    # the landing cell above it walkable; the player also needs clearance
    # over the current cell for any climb above one block.
    for height in range(1, max_climb + 1):
        if any(scene.get_block(candidate.translate(0, i, 0)) is None
               for i in range(0, height)):
            break
        if any(scene.get_block(current.translate(0, i, 0)) is not None
               for i in range(1, height)):
            break
        landing = candidate.translate(0, height, 0)
        if _walkable(scene, landing):
            yield landing
    # Drop: the fall path from the candidate column must be open air down to
    # a walkable landing cell.
    for drop in range(1, max_drop + 1):
        if any(scene.get_block(candidate.translate(0, -i, 0)) is not None
               for i in range(0, drop)):
            break
        landing = candidate.translate(0, -drop, 0)
        if _walkable(scene, landing):
            yield landing


def _walkable(scene: Scene, position: Vec3) -> bool:
    return (scene.get_block(position) is None and
            scene.get_block(position.translate(0, -1, 0)) is not None and
            scene.get_block(position.translate(0, 1, 0)) is None)
