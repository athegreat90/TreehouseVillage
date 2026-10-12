"""Inspect checksum-verified official server archives without executing Java.

Archive entries are read in memory, never extracted to filesystem paths.
Integer legacy pack formats and modern [major, minor] formats are preserved.
This evidence establishes formats, never functional datapack support.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Any, Mapping

from .compatibility import MetadataError

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_VERSION_BYTES = 1024 * 1024
MAX_NESTED_BYTES = 192 * 1024 * 1024


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _pack(value: Any) -> Any:
    if _nonnegative_int(value):
        return value
    if (isinstance(value, list) and len(value) == 2
            and all(_nonnegative_int(x) for x in value)):
        return value
    raise MetadataError(f"invalid pack format: {value!r}")


def _format(pack: Mapping[str, Any], kind: str) -> Any:
    if f"{kind}_major" in pack or f"{kind}_minor" in pack:
        return _pack([pack.get(f"{kind}_major"), pack.get(f"{kind}_minor")])
    return _pack(pack.get(kind))


def _read(z: zipfile.ZipFile, name: str, limit: int) -> bytes:
    entries = [entry for entry in z.infolist() if entry.filename == name]
    if len(entries) != 1:
        raise MetadataError(f"missing or duplicate archive entry: {name}")
    if entries[0].file_size > limit:
        raise MetadataError(f"archive entry exceeds size limit: {name}")
    with z.open(entries[0]) as entry:
        raw = entry.read(limit + 1)
    if len(raw) > limit:
        raise MetadataError(f"archive entry exceeds size limit: {name}")
    return raw


def _version_bytes(raw: bytes, version: str) -> tuple[bytes, str]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if "version.json" in z.namelist():
            return _read(z, "version.json", MAX_VERSION_BYTES), "version.json"
        lines = _read(z, "META-INF/versions.list", MAX_VERSION_BYTES).decode("utf-8").splitlines()
        matches = []
        for line in lines:
            fields = line.split("\t")
            if len(fields) == 3 and fields[1] == version:
                matches.append(fields[2])
        if len(matches) != 1:
            raise MetadataError(f"archive must identify exactly one nested server for id {version}")
        path = "META-INF/versions/" + matches[0]
        # No extraction occurs, but reject ambiguous paths to retain clear provenance.
        if any(part in ("", ".", "..") for part in path.split("/")) or "\\" in path:
            raise MetadataError("unsafe nested archive path")
        nested = _read(z, path, MAX_NESTED_BYTES)
    with zipfile.ZipFile(io.BytesIO(nested)) as z:
        return _read(z, "version.json", MAX_VERSION_BYTES), path + "!version.json"


def inspect_archive(raw: bytes, record: Mapping[str, Any]) -> dict[str, Any]:
    """Verify size/SHA1 and return exact-version embedded format evidence."""
    expected = record["server"]
    if len(raw) > MAX_ARCHIVE_BYTES or len(raw) != expected["size"]:
        raise MetadataError("server archive size mismatch or exceeds limit")
    if hashlib.sha1(raw).hexdigest() != expected["sha1"]:
        raise MetadataError("server archive SHA1 mismatch")
    try:
        payload, entry = _version_bytes(raw, record["id"])
        doc = json.loads(payload)
    except (zipfile.BadZipFile, RuntimeError, UnicodeDecodeError, ValueError, KeyError) as exc:
        raise MetadataError(f"invalid server archive: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("id") != record["id"]:
        raise MetadataError("embedded version id does not match requested id")
    data = doc.get("world_version")
    if not _nonnegative_int(data):
        raise MetadataError("invalid or missing world_version")
    pack = doc.get("pack_version")
    if not isinstance(pack, dict):
        raise MetadataError("invalid or missing pack_version")
    return {
        "id": record["id"],
        "formats": {"data_version": data, "data_pack_format": _format(pack, "data"),
                    "resource_pack_format": _format(pack, "resource")},
        "server_sha1_verified": True,
        "server_size_verified": True,
        "version_entry": entry,
        "embedded_version": doc,
        "support": "unverified",
        "runtime_qa": "pending",
    }
