from __future__ import annotations

from rapidnbt import CompoundTag, IntTag, ListTag, NbtCompressionType, NbtFileFormat, nbtio

from ..geometry.model import Block, Scene, Vec3


class StructureSerializer:
    """Serialize sparse scenes as Java structure-template NBT."""

    def __init__(self, *, data_version: int) -> None:
        if data_version < 0:
            raise ValueError("data_version must be non-negative")
        self.data_version = data_version

    @property
    def modern_palette(self) -> bool:
        return self.data_version >= 5023

    @staticmethod
    def _ints(values: list[int]) -> ListTag:
        return ListTag([IntTag(value) for value in values])

    def _palette_entry(self, block: Block) -> CompoundTag:
        name_key = "id" if self.modern_palette else "Name"
        properties_key = "properties" if self.modern_palette else "Properties"
        values: dict[str, object] = {name_key: block.name}
        if block.properties:
            values[properties_key] = CompoundTag(dict(block.properties))
        return CompoundTag(values)

    def _root(self, scene: Scene) -> CompoundTag:
        bounds = scene.bounds
        if bounds is None:
            raise ValueError("cannot serialize an empty scene")
        origin = bounds.minimum
        palette: list[Block] = []
        palette_index: dict[Block, int] = {}
        block_tags: list[CompoundTag] = []
        for position, block in scene.blocks():
            if block not in palette_index:
                palette_index[block] = len(palette)
                palette.append(block)
            local = position - origin
            block_tags.append(CompoundTag({
                "state": IntTag(palette_index[block]),
                "pos": self._ints([local.x, local.y, local.z]),
            }))
        return CompoundTag({
            "DataVersion": IntTag(self.data_version),
            "size": self._ints([bounds.size.x, bounds.size.y, bounds.size.z]),
            "palette": ListTag([self._palette_entry(block) for block in palette]),
            "blocks": ListTag(block_tags),
            "entities": ListTag(),
        })

    def dumps(self, scene: Scene) -> bytes:
        return nbtio.dumps(self._root(scene), format=NbtFileFormat.BIG_ENDIAN,
                            compression_type=NbtCompressionType.GZIP)
