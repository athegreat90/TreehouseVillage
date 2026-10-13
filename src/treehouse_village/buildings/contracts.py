from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..geometry.model import AABB, Scene, Vec3


@dataclass(frozen=True)
class FixtureRequirement:
    name: str
    position: Vec3
    block_name: str
    required_properties: Mapping[str, str] = ()

    def __post_init__(self) -> None:
        if not self.block_name.startswith("minecraft:"):
            raise ValueError(f"fixture block must be namespaced: {self.block_name}")
        object.__setattr__(self, "required_properties",
                           tuple(sorted(dict(self.required_properties).items())))


@dataclass(frozen=True)
class CoverageRequirement:
    """Explicit occupied cells; intentional openings must be excluded from the mask."""

    name: str
    positions: tuple[Vec3, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", tuple(sorted(set(self.positions))))


@dataclass(frozen=True)
class BuildingSpec:
    identifier: str
    category: str
    footprint: AABB
    entrance: Vec3
    fixtures: tuple[FixtureRequirement, ...] = ()
    coverage: tuple[CoverageRequirement, ...] = ()


@dataclass(frozen=True)
class BuildingIssue:
    code: str
    requirement: str
    position: Vec3
    message: str


def validate_building(scene: Scene, spec: BuildingSpec) -> tuple[BuildingIssue, ...]:
    issues: list[BuildingIssue] = []
    if not spec.footprint.contains(spec.entrance):
        issues.append(BuildingIssue(
            "entrance_outside_footprint", "entrance", spec.entrance,
            f"{spec.identifier} entrance lies outside its footprint",
        ))
    elif scene.get_block(spec.entrance) is None:
        issues.append(BuildingIssue(
            "missing_entrance", "entrance", spec.entrance,
            f"{spec.identifier} entrance has no block",
        ))
    for fixture in spec.fixtures:
        if not spec.footprint.contains(fixture.position):
            issues.append(BuildingIssue(
                "fixture_outside_footprint", fixture.name, fixture.position,
                f"{fixture.name} lies outside {spec.identifier} footprint",
            ))
            continue
        block = scene.get_block(fixture.position)
        if block is None or block.name != fixture.block_name:
            issues.append(BuildingIssue(
                "missing_fixture", fixture.name, fixture.position,
                f"{fixture.name} requires {fixture.block_name}",
            ))
        elif any(dict(block.properties).get(key) != value
                 for key, value in fixture.required_properties):
            issues.append(BuildingIssue(
                "fixture_state_mismatch", fixture.name, fixture.position,
                f"{fixture.name} has incorrect required block states",
            ))
    for requirement in spec.coverage:
        for position in requirement.positions:
            if not spec.footprint.contains(position):
                issues.append(BuildingIssue(
                    "coverage_outside_footprint", requirement.name, position,
                    f"{requirement.name} coverage lies outside {spec.identifier} footprint",
                ))
                continue
            block = scene.get_block(position)
            if block is None or block.name in {
                "minecraft:air", "minecraft:cave_air", "minecraft:void_air",
            }:
                issues.append(BuildingIssue(
                    "missing_coverage", requirement.name, position,
                    f"{requirement.name} requires an occupied cell at {position}",
                ))
    return tuple(issues)
