from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from treehouse_village import compatibility as c

TARGETS = ("26.1.2", "26.2", "26.3")


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def version_doc(vid: str, vtype: str = "release", **extra) -> bytes:
    doc = {
        "id": vid,
        "type": vtype,
        "javaVersion": {"component": "java-runtime-x", "majorVersion": 25},
        "downloads": {
            "server": {"sha1": "a" * 40, "size": 123, "url": f"https://piston-data.mojang.com/v1/objects/{'a' * 40}/server.jar"}
        },
    }
    doc.update(extra)
    return json.dumps(doc).encode()


def make_world(ids=TARGETS, types=None, **extra):
    """Return (manifest_bytes, {url: bytes}) for a synthetic Mojang manifest."""
    types = types or {}
    docs, entries = {}, []
    for vid in ids:
        body = version_doc(vid, types.get(vid, "release"), **extra)
        url = f"https://piston-meta.mojang.com/v1/packages/{sha1(body)}/{vid}.json"
        docs[url] = body
        entries.append({"id": vid, "type": types.get(vid, "release"), "url": url, "sha1": sha1(body), "releaseTime": "2026-01-01T00:00:00+00:00", "time": "2026-01-02T00:00:00+00:00"})
    # Decoys that must never match by prefix or substring.
    entries.append({"id": "26.2-rc-1", "type": "snapshot", "url": "https://piston-meta.mojang.com/x.json", "sha1": "b" * 40})
    return json.dumps({"versions": entries}).encode(), docs


def fetcher(docs, manifest):
    def fetch(url, **_):
        if url == c.MANIFEST_URL:
            return manifest
        if url not in docs:
            raise c.FetchError(f"unexpected {url}")
        return docs[url]
    return fetch


def test_exact_ids_resolved_and_decoys_ignored():
    manifest, docs = make_world()
    entries = c.parse_manifest(manifest)
    found = c.resolve_targets(entries, TARGETS)
    assert [found[t]["id"] for t in TARGETS] == list(TARGETS)
    assert c.resolve_targets(entries, ("26.2-rc",))["26.2-rc"] is None


def test_absent_versions_are_explicit_unavailable_without_substitution():
    manifest, docs = make_world(ids=("26.1.2",))
    result = c.discover(TARGETS, fetcher(docs, manifest))
    assert result["26.1.2"]["status"] == "metadata_found"
    for vid in ("26.2", "26.3"):
        rec = result[vid]
        assert rec["status"] == "unavailable"
        assert rec["server"] is None and rec["java"] is None
        assert rec["support"] == "unsupported_unavailable"


def test_snapshot_type_is_recorded_not_promoted():
    manifest, docs = make_world(types={"26.2": "snapshot"})
    rec = c.discover(TARGETS, fetcher(docs, manifest))["26.2"]
    assert rec["official_type"] == "snapshot"
    assert rec["release_status"] == "not_official_release"
    assert c.discover(TARGETS, fetcher(docs, manifest))["26.3"]["release_status"] == "official_release"


def test_found_metadata_is_not_support_and_formats_unknown():
    manifest, docs = make_world()
    rec = c.discover(TARGETS, fetcher(docs, manifest))["26.3"]
    assert rec["support"] == "unverified"
    assert rec["runtime_qa"] == "pending"
    assert rec["java"] == {"component": "java-runtime-x", "major_version": 25}
    assert rec["server"]["sha1"] == "a" * 40 and rec["server"]["url"].endswith("server.jar")
    assert rec["formats"] == {"data_version": "unknown", "data_pack_format": "unknown", "resource_pack_format": "unknown"}


def test_format_fields_only_recorded_when_authoritative_metadata_states_them():
    manifest, docs = make_world(world_version=4321, pack_version={"data": 99, "resource": 77})
    rec = c.discover(TARGETS, fetcher(docs, manifest))["26.3"]
    assert rec["formats"] == {"data_version": 4321, "data_pack_format": 99, "resource_pack_format": 77}
    manifest, docs = make_world(world_version="4321", pack_version={"data": True})
    rec = c.discover(TARGETS, fetcher(docs, manifest))["26.3"]
    assert set(rec["formats"].values()) == {"unknown"}


@pytest.mark.parametrize("bad", [b"not json", b"[]", b'{"versions": {}}', b'{"versions": [{"id": 5}]}',
                                 b'{"versions": [{"id": "26.2", "type": "release", "url": "https://piston-meta.mojang.com/a", "sha1": "zz"}]}'])
def test_malformed_manifest_rejected(bad):
    with pytest.raises(c.MetadataError):
        c.parse_manifest(bad)


def test_duplicate_target_ids_rejected():
    entry = {"id": "26.2", "type": "release", "url": "https://piston-meta.mojang.com/a", "sha1": "a" * 40}
    with pytest.raises(c.MetadataError):
        c.parse_manifest(json.dumps({"versions": [entry, entry]}).encode())


def test_sha1_mismatch_rejected():
    manifest, docs = make_world()
    url = next(u for u in docs if u.endswith("/26.3.json"))
    docs[url] = docs[url] + b" "
    with pytest.raises(c.MetadataError, match="SHA1"):
        c.discover(TARGETS, fetcher(docs, manifest))


def test_version_metadata_must_match_entry_and_have_server_and_java():
    entry = {"id": "26.3", "type": "release", "url": "u", "sha1": ""}
    for body in (version_doc("26.2"), version_doc("26.3", "snapshot"), json.dumps({"id": "26.3", "type": "release"}).encode()):
        e = dict(entry, sha1=sha1(body))
        with pytest.raises(c.MetadataError):
            c.build_record(e, body)


def test_non_mojang_or_insecure_urls_rejected_before_network():
    for url in ("http://piston-meta.mojang.com/a", "https://evil.example/a", "file:///etc/passwd"):
        with pytest.raises(c.FetchError):
            c.fetch_bytes(url)


def test_failed_network_preserves_prior_evidence(tmp_path: Path):
    manifest, docs = make_world()
    c.run(tmp_path, TARGETS, fetcher(docs, manifest))
    ev = tmp_path / "build/compatibility/26.3.json"
    prof = tmp_path / "config/versions/26.3.json"
    before = (ev.read_bytes(), prof.read_bytes())

    def boom(url, **_):
        raise c.FetchError("network down")

    report = c.run(tmp_path, TARGETS, boom)
    assert report["ok"] is False
    assert (ev.read_bytes(), prof.read_bytes()) == before

    # Manifest fine but one version document fails: only that target keeps old evidence.
    docs2 = {u: b for u, b in docs.items() if not u.endswith("/26.2.json")}
    report = c.run(tmp_path, TARGETS, fetcher(docs2, manifest))
    assert report["targets"]["26.2"]["outcome"] == "failed"
    assert (tmp_path / "build/compatibility/26.2.json").exists()
    assert (ev.read_bytes(), prof.read_bytes()) == before


def test_output_is_stable_and_atomic(tmp_path: Path):
    manifest, docs = make_world()
    c.run(tmp_path, TARGETS, fetcher(docs, manifest))
    first = {p.name: p.read_bytes() for p in (tmp_path / "build/compatibility").glob("26*.json")}
    c.run(tmp_path, TARGETS, fetcher(docs, manifest))
    assert first == {p.name: p.read_bytes() for p in (tmp_path / "build/compatibility").glob("26*.json")}
    assert not list(tmp_path.rglob("*.tmp"))
    assert first["26.3.json"].endswith(b"\n") and json.loads(first["26.3.json"])["id"] == "26.3"


@pytest.mark.parametrize("vid", ["../escape", "26.3/../../x", "a\b", "", "26.3\x00"])
def test_output_confined_to_root(tmp_path: Path, vid):
    with pytest.raises(c.ConfinementError):
        c.write_json_atomic(tmp_path, "build/compatibility", vid, {"a": 1})
    assert not (tmp_path.parent / "escape.json").exists()


def test_symlink_or_root_escape_rejected(tmp_path: Path):
    with pytest.raises(c.ConfinementError):
        c.write_json_atomic(tmp_path, "../outside", "26.3", {})
    with pytest.raises(c.ConfinementError):
        c.write_json_atomic(tmp_path, "src", "26.3", {})  # only evidence/profile dirs allowed
