"""Minecraft version compatibility discovery from Mojang's official metadata.

Pure parsing/record building is separate from the network layer (``fetch_bytes``).
Finding metadata is NOT support: every record is ``unverified`` with runtime QA
``pending``, and format numbers stay ``"unknown"`` unless Mojang's version
metadata states them. Requested versions are matched by EXACT id only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
DEFAULT_TARGETS = ("26.1.2", "26.2", "26.3")
ALLOWED_HOSTS = frozenset({"piston-meta.mojang.com", "piston-data.mojang.com"})
MANIFEST_MAX_BYTES = 8 * 1024 * 1024
VERSION_MAX_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT = 20.0
EVIDENCE_DIR = "build/compatibility"
PROFILE_DIR = "config/versions"
UNKNOWN = "unknown"
SCHEMA_VERSION = 1

_SHA1 = re.compile(r"[0-9a-f]{40}")
_NAME = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")


class CompatibilityError(Exception):
    """Base class for discovery failures."""


class FetchError(CompatibilityError):
    """Network/transport failure or a refused URL."""


class MetadataError(CompatibilityError):
    """Metadata is malformed, inconsistent or fails integrity checks."""


class ConfinementError(CompatibilityError):
    """An output path would leave the allowed project locations."""


Fetch = Callable[..., bytes]


# --------------------------------------------------------------------- network
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


def check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise FetchError(f"refusing non-HTTPS or non-Mojang URL: {url!r}")


def fetch_bytes(url: str, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = VERSION_MAX_BYTES) -> bytes:
    """GET ``url`` with a timeout and hard size cap; no redirects."""
    check_url(url)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "treehouse-village-discovery/0"}), timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FetchError(f"request failed for {url}: {exc}") from exc
    if len(data) > max_bytes:
        raise FetchError(f"response exceeds {max_bytes} bytes: {url}")
    return data


# --------------------------------------------------------------- pure parsing
def _load_json(data: bytes, what: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MetadataError(f"{what} is not valid JSON: {exc}") from exc


def parse_manifest(data: bytes) -> dict[str, dict[str, Any]]:
    """Validate manifest v2 bytes and return ``{id: entry}``."""
    doc = _load_json(data, "manifest")
    if not isinstance(doc, dict) or not isinstance(doc.get("versions"), list):
        raise MetadataError("manifest must be an object with a 'versions' list")
    entries: dict[str, dict[str, Any]] = {}
    for raw in doc["versions"]:
        if not isinstance(raw, dict) or not all(isinstance(raw.get(k), str) for k in ("id", "type", "url", "sha1")):
            raise MetadataError(f"malformed manifest entry: {str(raw)[:120]}")
        if not _SHA1.fullmatch(raw["sha1"]):
            raise MetadataError(f"manifest entry {raw['id']!r} has an invalid sha1")
        if raw["id"] in entries:
            raise MetadataError(f"duplicate manifest id {raw['id']!r}")
        entries[raw["id"]] = raw
    return entries


def resolve_targets(entries: Mapping[str, dict[str, Any]], targets: Iterable[str]) -> dict[str, dict[str, Any] | None]:
    """Exact-id lookup only; absent targets map to ``None`` (never substituted)."""
    return {t: entries.get(t) for t in targets}


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _formats(doc: Mapping[str, Any]) -> dict[str, Any]:
    pack = doc.get("pack_version") if isinstance(doc.get("pack_version"), dict) else {}
    values = {
        "data_version": _int(doc.get("world_version")),
        "data_pack_format": _int(pack.get("data")),
        "resource_pack_format": _int(pack.get("resource")),
    }
    return {k: (UNKNOWN if v is None else v) for k, v in values.items()}


def build_record(entry: Mapping[str, Any], version_bytes: bytes) -> dict[str, Any]:
    """Verify version metadata against its manifest entry and build a record."""
    if hashlib.sha1(version_bytes).hexdigest() != entry["sha1"]:
        raise MetadataError(f"SHA1 mismatch for {entry['id']}: metadata does not match manifest")
    doc = _load_json(version_bytes, f"metadata for {entry['id']}")
    if not isinstance(doc, dict) or doc.get("id") != entry["id"]:
        raise MetadataError(f"metadata id does not match requested {entry['id']!r}")
    if doc.get("type") != entry["type"]:
        raise MetadataError(f"metadata type {doc.get('type')!r} disagrees with manifest {entry['type']!r}")
    server = (doc.get("downloads") or {}).get("server") if isinstance(doc.get("downloads"), dict) else None
    if not (isinstance(server, dict) and isinstance(server.get("url"), str) and isinstance(server.get("sha1"), str)
            and _SHA1.fullmatch(server["sha1"]) and _int(server.get("size")) and server["size"] > 0):
        raise MetadataError(f"{entry['id']} lacks a valid server download (url/sha1/size)")
    check_url(server["url"])
    java = doc.get("javaVersion")
    if not (isinstance(java, dict) and isinstance(java.get("component"), str) and _int(java.get("majorVersion"))):
        raise MetadataError(f"{entry['id']} lacks a valid javaVersion")
    return {
        "schema_version": SCHEMA_VERSION,
        "id": entry["id"],
        "status": "metadata_found",
        "official_type": entry["type"],
        "release_status": "official_release" if entry["type"] == "release" else "not_official_release",
        "support": "unverified",
        "runtime_qa": "pending",
        "java": {"component": java["component"], "major_version": java["majorVersion"]},
        "server": {"url": server["url"], "sha1": server["sha1"], "size": server["size"]},
        "formats": _formats(doc),
        "sources": {
            "manifest_url": MANIFEST_URL,
            "version_metadata_url": entry["url"],
            "version_metadata_sha1": entry["sha1"],
            "version_metadata_sha1_verified": True,
            "release_time": entry.get("releaseTime"),
            "manifest_time": entry.get("time"),
        },
    }


def unavailable_record(version_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": version_id,
        "status": "unavailable",
        "official_type": None,
        "release_status": "unavailable",
        "support": "unsupported_unavailable",
        "runtime_qa": "pending",
        "java": None,
        "server": None,
        "formats": {k: UNKNOWN for k in ("data_version", "data_pack_format", "resource_pack_format")},
        "sources": {"manifest_url": MANIFEST_URL, "note": "exact id absent from official manifest"},
    }


def profile_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Profile = record without source detail, pointing at its evidence file."""
    profile = {k: v for k, v in record.items() if k != "sources"}
    profile["evidence"] = f"{EVIDENCE_DIR}/{record['id']}.json"
    return profile


# ------------------------------------------------------------ orchestration
def _record_for(target: str, entry: Mapping[str, Any] | None, fetch: Fetch, timeout: float) -> dict[str, Any]:
    if entry is None:
        return unavailable_record(target)
    return build_record(entry, fetch(entry["url"], timeout=timeout, max_bytes=VERSION_MAX_BYTES))


def discover(targets: Iterable[str], fetch: Fetch = fetch_bytes, timeout: float = DEFAULT_TIMEOUT) -> dict[str, dict[str, Any]]:
    """Fetch and verify records for ``targets``; raises on any failure."""
    entries = parse_manifest(fetch(MANIFEST_URL, timeout=timeout, max_bytes=MANIFEST_MAX_BYTES))
    return {t: _record_for(t, e, fetch, timeout) for t, e in resolve_targets(entries, tuple(targets)).items()}


# ------------------------------------------------------------------- output
def _confined_dir(root: Path, rel_dir: str) -> Path:
    if rel_dir not in (EVIDENCE_DIR, PROFILE_DIR):
        raise ConfinementError(f"output directory not allowed: {rel_dir!r}")
    base = root.resolve()
    target = (base / rel_dir).resolve()
    if base not in target.parents:
        raise ConfinementError(f"{rel_dir!r} resolves outside the project root")
    return target


def write_json_atomic(root: Path, rel_dir: str, name: str, data: Any) -> Path:
    """Write stable JSON to ``<root>/<rel_dir>/<name>.json`` via temp file + replace."""
    if not _NAME.fullmatch(name):
        raise ConfinementError(f"unsafe file name: {name!r}")
    directory = _confined_dir(root, rel_dir)
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"{name}.json"
    payload = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, final)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return final


def run(root: Path, targets: Iterable[str], fetch: Fetch = fetch_bytes, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Discover ``targets`` and write evidence/profiles; failures keep prior files."""
    root = Path(root)
    targets = tuple(targets)
    for t in targets:
        if not _NAME.fullmatch(t):
            raise ConfinementError(f"unsafe target id: {t!r}")
    report: dict[str, Any] = {"ok": True, "manifest_url": MANIFEST_URL, "targets": {}}
    try:
        entries = parse_manifest(fetch(MANIFEST_URL, timeout=timeout, max_bytes=MANIFEST_MAX_BYTES))
    except CompatibilityError as exc:
        report["ok"] = False
        report["error"] = f"manifest: {exc}"
        write_json_atomic(root, EVIDENCE_DIR, "last-run", report)
        return report
    for target, entry in resolve_targets(entries, targets).items():
        try:
            record = _record_for(target, entry, fetch, timeout)
        except CompatibilityError as exc:
            kind = "rejected" if isinstance(exc, MetadataError) else "failed"
            report["ok"] = False
            report["targets"][target] = {"outcome": kind, "error": str(exc), "prior_evidence_kept": True}
            continue
        write_json_atomic(root, EVIDENCE_DIR, target, record)
        write_json_atomic(root, PROFILE_DIR, target, profile_from_record(record))
        report["targets"][target] = {"outcome": record["status"]}
    write_json_atomic(root, EVIDENCE_DIR, "last-run", report)
    return report
