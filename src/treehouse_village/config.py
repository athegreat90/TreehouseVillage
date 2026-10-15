"""Declarative village configuration for deterministic composition.

A village is fully described by its trees, building placements, bridge
placements and named route destinations. The same configuration and seed
always regenerate the same geometry; nothing is derived from ambient state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .geometry.model import Vec3

BUILDING_KINDS = frozenset({"home", "civic", "outdoor", "hall"})


def _vec(value: Sequence[Any], label: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be an array of three integers")
    return Vec3(int(value[0]), int(value[1]), int(value[2]))


@dataclass(frozen=True)
class TreePlacement:
    """One giant tree: position, trunk shape and the bridge landing edge."""

    name: str
    x: int
    z: int
    platform_level: int
    height: int
    seed: int
    landing: tuple[int, int]
    radius: int = 4

    def __post_init__(self) -> None:
        if not self.name.startswith("tree_"):
            raise ValueError(f"tree name must start with 'tree_': {self.name!r}")
        if self.platform_level < 3:
            raise ValueError(f"{self.name}: platform_level must be at least 3")
        if self.height < self.platform_level + 3:
            raise ValueError(f"{self.name}: height must leave canopy room above the platform")
        if self.radius < 2:
            raise ValueError(f"{self.name}: radius must be at least 2")
        if len(self.landing) != 2:
            raise ValueError(f"{self.name}: landing must be an [dx, dz] offset")
        dx, dz = int(self.landing[0]), int(self.landing[1])
        if dx * dx + dz * dz > self.radius * self.radius:
            raise ValueError(f"{self.name}: landing ({dx}, {dz}) lies outside the platform")
        object.__setattr__(self, "landing", (dx, dz))

    @property
    def origin(self) -> Vec3:
        return Vec3(self.x, 0, self.z)

    @property
    def platform_cell(self) -> Vec3:
        """The platform edge cell a bridge must end on."""
        dx, dz = self.landing
        return Vec3(self.x + dx, self.platform_level, self.z + dz)

    @property
    def node_position(self) -> Vec3:
        """The standing cell above the landing edge."""
        return self.platform_cell.translate(0, 1, 0)


@dataclass(frozen=True)
class BuildingPlacement:
    """One building placed at an absolute in-footprint origin."""

    kind: str
    design: str
    origin: Vec3
    node: str
    node_position: Vec3 | None = None

    def __post_init__(self) -> None:
        if self.kind not in BUILDING_KINDS:
            raise ValueError(
                f"building kind must be one of {sorted(BUILDING_KINDS)}: {self.kind!r}")
        if not self.design:
            raise ValueError(f"building {self.node!r} must name a design")
        if not self.node:
            raise ValueError("building node name must be non-empty")


@dataclass(frozen=True)
class BridgePlacement:
    """One axis-aligned suspension bridge between two occupied anchor cells."""

    start: Vec3
    end: Vec3
    width: int = 5
    name: str = ""

    def __post_init__(self) -> None:
        dx = self.end.x - self.start.x
        dz = self.end.z - self.start.z
        if (dx == 0) == (dz == 0):
            raise ValueError(
                f"bridge {self.name or self.start!r} must be axis-aligned along one axis")
        if self.width < 3 or self.width % 2 == 0:
            raise ValueError(f"bridge {self.name or self.start!r} width must be an odd integer >= 3")
        span = abs(dx) or abs(dz)
        if span < 3:
            raise ValueError(f"bridge {self.name or self.start!r} span must be at least 3")
        dy = abs(self.end.y - self.start.y)
        if dy * 2 > span:
            raise ValueError(f"bridge {self.name or self.start!r} slope exceeds its span")


@dataclass(frozen=True)
class VillageConfig:
    """Complete declarative description of one village variant."""

    variant: str
    width: int
    depth: int
    seed: int
    entrance: str
    trees: tuple[TreePlacement, ...]
    buildings: tuple[BuildingPlacement, ...]
    bridges: tuple[BridgePlacement, ...]
    ground_block: str = "minecraft:grass_block"

    def __post_init__(self) -> None:
        object.__setattr__(self, "trees", tuple(self.trees))
        object.__setattr__(self, "buildings", tuple(self.buildings))
        object.__setattr__(self, "bridges", tuple(self.bridges))
        if not self.variant:
            raise ValueError("variant must be non-empty")
        if self.width < 32 or self.depth < 32:
            raise ValueError("village footprint must be at least 32 blocks per side")
        if not self.entrance:
            raise ValueError("entrance must name a building node")
        if not self.trees:
            raise ValueError("village needs at least one tree")
        if not self.buildings:
            raise ValueError("village needs at least one building")
        if not self.bridges:
            raise ValueError("village needs at least one bridge")
        if not self.ground_block.startswith("minecraft:"):
            raise ValueError(f"ground_block must be namespaced: {self.ground_block!r}")

        tree_names = [tree.name for tree in self.trees]
        if len(set(tree_names)) != len(tree_names):
            raise ValueError("tree names must be unique")
        node_names = [building.node for building in self.buildings]
        if len(set(node_names)) != len(node_names):
            raise ValueError("building node names must be unique")
        overlap = set(tree_names) & set(node_names)
        if overlap:
            raise ValueError(f"tree and building node names collide: {sorted(overlap)}")
        if self.entrance not in node_names:
            raise ValueError(
                f"entrance {self.entrance!r} is not a building node: {sorted(node_names)}")

        bridge_ends = {bridge.end for bridge in self.bridges}
        for tree in self.trees:
            if tree.platform_cell not in bridge_ends:
                raise ValueError(
                    f"{tree.name}: no bridge lands on platform cell {tree.platform_cell}")

    @property
    def node_names(self) -> tuple[str, ...]:
        return tuple(building.node for building in self.buildings) + tuple(
            tree.name for tree in self.trees)

    @classmethod
    def _load(cls, path: str | Path, *, variant: str) -> "VillageConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: configuration root must be a JSON object")
        return cls._from_mapping(data, variant=variant, source=str(path))

    @classmethod
    def _from_mapping(cls, data: Mapping[str, Any], *, variant: str, source: str) -> "VillageConfig":
        if data.get("variant") != variant:
            raise ValueError(f"{source}: variant must be {variant!r}")
        try:
            trees = tuple(TreePlacement(
                name=str(entry["name"]),
                x=int(entry["x"]),
                z=int(entry["z"]),
                platform_level=int(entry["platform_level"]),
                height=int(entry["height"]),
                seed=int(entry["seed"]),
                landing=tuple(entry["landing"]),
                radius=int(entry.get("radius", 4)),
            ) for entry in data.get("trees", ()))
            buildings = tuple(BuildingPlacement(
                kind=str(entry["kind"]),
                design=str(entry["design"]),
                origin=_vec(entry["origin"], f"{source}: building origin"),
                node=str(entry["node"]),
                node_position=(_vec(entry["node_position"],
                                    f"{source}: node_position")
                               if "node_position" in entry else None),
            ) for entry in data.get("buildings", ()))
            bridges = tuple(BridgePlacement(
                start=_vec(entry["start"], f"{source}: bridge start"),
                end=_vec(entry["end"], f"{source}: bridge end"),
                width=int(entry.get("width", 5)),
                name=str(entry.get("name", "")),
            ) for entry in data.get("bridges", ()))
            return cls(
                variant=str(data["variant"]),
                width=int(data["width"]),
                depth=int(data["depth"]),
                seed=int(data.get("seed", 0)),
                entrance=str(data["entrance"]),
                trees=trees,
                buildings=buildings,
                bridges=bridges,
                ground_block=str(data.get("ground_block", "minecraft:grass_block")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{source}: invalid configuration: {error}") from error


class CompactConfig(VillageConfig):
    """The 96x96 Compact village variant."""

    @classmethod
    def from_json(cls, path: str | Path) -> "CompactConfig":
        # cls is CompactConfig, so the shared loader builds this subclass.
        return cls._load(path, variant="compact")


class MegaConfig(VillageConfig):
    """The 176x176 Mega village variant."""

    @classmethod
    def from_json(cls, path: str | Path) -> "MegaConfig":
        return cls._load(path, variant="mega")
