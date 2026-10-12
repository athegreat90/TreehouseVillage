"""Exact-version archive evidence must fail closed before server execution."""
import hashlib
import io
import json
import zipfile

import pytest

from treehouse_village.server_archive import inspect_archive
from treehouse_village.compatibility import MetadataError


def archive(version="26.1.2", data=5000, pack=None, nested=False):
    payload = {"id": version, "world_version": data,
               "pack_version": pack or {"data": [101, 1], "resource": [84, 0]}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("version.json", json.dumps(payload))
    raw = stream.getvalue()
    if nested:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("META-INF/versions.list", "hash\t26.1.2\t26.1.2/server.jar\n")
            z.writestr("META-INF/versions/26.1.2/server.jar", raw)
        raw = stream.getvalue()
    return raw


def record(raw):
    return {"id": "26.1.2", "server": {"size": len(raw),
            "sha1": hashlib.sha1(raw).hexdigest()}}


@pytest.mark.parametrize("nested", [False, True])
def test_verified_version_and_formats(nested):
    raw = archive(nested=nested)
    result = inspect_archive(raw, record(raw))
    assert result["id"] == "26.1.2"
    assert result["formats"] == {"data_version": 5000,
        "data_pack_format": [101, 1], "resource_pack_format": [84, 0]}
    assert result["server_sha1_verified"] is True
    assert result["support"] == "unverified"
    assert result["runtime_qa"] == "pending"


@pytest.mark.parametrize("field,value", [("size", 1), ("sha1", "0" * 40)])
def test_wrong_archive_integrity_rejected(field, value):
    raw = archive()
    expected = record(raw)
    expected["server"][field] = value
    with pytest.raises(MetadataError, match="size|SHA1"):
        inspect_archive(raw, expected)


def test_wrong_version_rejected():
    raw = archive(version="26.2")
    with pytest.raises(MetadataError, match="id"):
        inspect_archive(raw, record(raw))


@pytest.mark.parametrize("data", [None, True, -1, "5000"])
def test_invalid_data_version_rejected(data):
    raw = archive(data=data)
    with pytest.raises(MetadataError, match="world_version"):
        inspect_archive(raw, record(raw))


@pytest.mark.parametrize("pack", [{"data": "101", "resource": 84},
    {"data": [101], "resource": 84}, {"data": [101, True], "resource": 84},
    {"data": -1, "resource": 84}])
def test_invalid_pack_format_rejected(pack):
    raw = archive(pack=pack)
    with pytest.raises(MetadataError, match="pack"):
        inspect_archive(raw, record(raw))


def test_verified_modern_major_minor_schema():
    raw = archive(data=4790, pack={"resource_major": 84, "resource_minor": 0,
                                "data_major": 101, "data_minor": 1})
    result = inspect_archive(raw, record(raw))
    assert result["formats"] == {"data_version": 4790,
        "data_pack_format": [101, 1], "resource_pack_format": [84, 0]}
    assert result["support"] == "unverified"


@pytest.mark.parametrize("minor", [None, True, -1, "1"])
def test_invalid_modern_minor_rejected(minor):
    raw = archive(pack={"data_major": 101, "data_minor": minor,
                        "resource_major": 84, "resource_minor": 0})
    with pytest.raises(MetadataError, match="pack"):
        inspect_archive(raw, record(raw))


def test_integer_formats_preserved():
    raw = archive(pack={"data": 101, "resource": 84})
    assert inspect_archive(raw, record(raw))["formats"]["data_pack_format"] == 101


def test_non_zip_rejected():
    raw = b"not a jar"
    with pytest.raises(MetadataError, match="archive"):
        inspect_archive(raw, record(raw))


def test_duplicate_version_files_rejected():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("version.json", "{}")
        with pytest.warns(UserWarning):
            z.writestr("version.json", "{}")
    raw = stream.getvalue()
    with pytest.raises(MetadataError, match="duplicate"):
        inspect_archive(raw, record(raw))
