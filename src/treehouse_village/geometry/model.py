from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, order=True)
class Vec3:
    x: int
    y: int
    z: int

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def translate(self, x: int, y: int, z: int) -> "Vec3":
        return self + Vec3(x, y, z)


@dataclass(frozen=True)
class AABB:
    minimum: Vec3
    maximum: Vec3

    def __post_init__(self) -> None:
        if (self.minimum.x > self.maximum.x or
                self.minimum.y > self.maximum.y or
                self.minimum.z > self.maximum.z):
            raise ValueError("minimum must not exceed maximum")

    @property
    def size(self) -> Vec3:
        return Vec3(self.maximum.x - self.minimum.x + 1,
                    self.maximum.y - self.minimum.y + 1,
                    self.maximum.z - self.minimum.z + 1)

    def contains(self, position: Vec3) -> bool:
        return (self.minimum.x <= position.x <= self.maximum.x and
                self.minimum.y <= position.y <= self.maximum.y and
                self.minimum.z <= position.z <= self.maximum.z)


@dataclass(frozen=True)
class Block:
    name: str
    properties: Mapping[str, str] = ()

    def __post_init__(self) -> None:
        if not self.name.startswith("minecraft:"):
            raise ValueError(f"block name must be namespaced: {self.name}")
        object.__setattr__(self, "properties", tuple(sorted(dict(self.properties).items())))


class Scene:
    def __init__(self, blocks: Mapping[Vec3, Block] | None = None) -> None:
        self._blocks: dict[Vec3, Block] = dict(blocks or {})

    def set_block(self, position: Vec3, block: Block) -> None:
        existing = self._blocks.get(position)
        if existing is not None and existing != block:
            raise ValueError(f"conflicting block at {position}: {existing.name} vs {block.name}")
        self._blocks[position] = block

    def get_block(self, position: Vec3) -> Block | None:
        return self._blocks.get(position)

    def blocks(self) -> tuple[tuple[Vec3, Block], ...]:
        return tuple(sorted(self._blocks.items()))

    @property
    def bounds(self) -> AABB | None:
        if not self._blocks:
            return None
        positions = tuple(self._blocks)
        return AABB(Vec3(min(p.x for p in positions), min(p.y for p in positions), min(p.z for p in positions)),
                    Vec3(max(p.x for p in positions), max(p.y for p in positions), max(p.z for p in positions)))

    def translated(self, offset: Vec3) -> "Scene":
        return Scene({position + offset: block for position, block in self._blocks.items()})

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Scene) and self._blocks == other._blocks

    def __len__(self) -> int:
        return len(self._blocks)
