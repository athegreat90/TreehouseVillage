"""Public dependency probes, not village assets or game-support claims."""
from importlib.metadata import version
from io import BytesIO
import gzip
import struct

import pytest


def test_stable_nbt_dependency_imports():
    import rapidnbt

    assert version("rapidnbt") == "1.3.5"
    assert rapidnbt.CompoundTag is not None


def _read_java_nbt(raw):
    """Small independent wire oracle for these fixtures' four tag types."""
    stream = BytesIO(raw)

    def take(length):
        value = stream.read(length)
        assert len(value) == length
        return value

    def integer():
        return struct.unpack(">i", take(4))[0]

    def string():
        length = struct.unpack(">H", take(2))[0]
        return take(length).decode("ascii")

    def payload(tag):
        if tag == 3:
            return integer()
        if tag == 8:
            return string()
        if tag == 9:
            element = take(1)[0]
            length = integer()
            assert 0 <= length <= 100
            return (element, [payload(element) for _ in range(length)])
        if tag == 10:
            values = {}
            while True:
                child = take(1)[0]
                if child == 0:
                    return values
                name = string()
                assert name not in values
                values[name] = (child, payload(child))
        raise AssertionError(f"Unexpected fixture tag type: {tag}")

    assert take(1) == b"\x0a"
    assert string() == ""  # Java's named root, not a Bedrock header.
    root = payload(10)
    assert stream.read() == b""
    return root


@pytest.mark.parametrize("compressed", [False, True])
def test_java_big_endian_integer_matches_independent_wire_bytes(compressed):
    from rapidnbt import CompoundTag, IntTag, NbtCompressionType, NbtFileFormat, nbtio

    root = CompoundTag({"value": IntTag(0x01020304)})
    compression = NbtCompressionType.GZIP if compressed else NbtCompressionType.NONE
    result = nbtio.dumps(root, format=NbtFileFormat.BIG_ENDIAN,
                         compression_type=compression)
    if compressed:
        assert result[:2] == b"\x1f\x8b"
        result = gzip.decompress(result)
    assert result == b"\x0a\x00\x00\x03\x00\x05value\x01\x02\x03\x04\x00"


@pytest.mark.parametrize("data_version", [4790, 4903, 5023])
def test_compressed_structure_fixture_has_exact_java_types(tmp_path, data_version):
    from rapidnbt import (
        CompoundTag, IntTag, ListTag, NbtCompressionType, NbtFileFormat, nbtio,
    )

    def ints(values):
        return ListTag([IntTag(value) for value in values])

    root = CompoundTag({
        "DataVersion": IntTag(data_version),
        "size": ints([1, 2, 1]),
        "palette": ListTag([
            CompoundTag({"Name": "minecraft:jungle_log",
                         "Properties": CompoundTag({"axis": "y"})}),
            CompoundTag({"Name": "minecraft:lantern",
                         "Properties": CompoundTag({"hanging": "false",
                                                    "waterlogged": "false"})}),
        ]),
        "blocks": ListTag([
            CompoundTag({"state": IntTag(0), "pos": ints([0, 0, 0])}),
            CompoundTag({"state": IntTag(1), "pos": ints([0, 1, 0])}),
        ]),
        "entities": ListTag(),
    })
    destination = tmp_path / "toolchain_probe.nbt"
    assert nbtio.dump(root, destination, format=NbtFileFormat.BIG_ENDIAN,
                      compression_type=NbtCompressionType.GZIP) is True
    encoded = destination.read_bytes()
    assert encoded[:2] == b"\x1f\x8b"
    decoded = _read_java_nbt(gzip.decompress(encoded))
    assert set(decoded) == {"DataVersion", "size", "palette", "blocks", "entities"}
    assert decoded["DataVersion"] == (3, data_version)
    assert decoded["size"] == (9, (3, [1, 2, 1]))
    assert decoded["palette"] == (9, (10, [
        {"Name": (8, "minecraft:jungle_log"),
         "Properties": (10, {"axis": (8, "y")})},
        {"Name": (8, "minecraft:lantern"),
         "Properties": (10, {"hanging": (8, "false"), "waterlogged": (8, "false")})},
    ]))
    assert decoded["blocks"] == (9, (10, [
        {"state": (3, 0), "pos": (9, (3, [0, 0, 0]))},
        {"state": (3, 1), "pos": (9, (3, [0, 1, 0]))},
    ]))
    assert decoded["entities"][0] == 9
    assert decoded["entities"][1][1] == []
