"""T10: release packaging — evidence-gated version ZIPs (S11, S12).

S11: every ZIP must carry `pack.mcmeta` at the archive root (never inside
an extra wrapping folder), and a version-labeled artifact may only be
produced when the compatibility evidence actually justifies it: the
tracked evidence must exist, match the verified profile formats, and
record a verified server sha1. S12: release files get checksums
(`SHA256SUMS.txt`, standard `<sha256>  <filename>` lines, idempotent on
rebuild).

Everything here is pure file/JSON work: no Minecraft run is claimed.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from treehouse_village.packaging import (ReleaseError, build_release_zip,
                                         update_checksums,
                                         verify_release_evidence)

PROFILE_FORMATS = {"data_pack_format": [101, 1], "data_version": 4790,
                   "resource_pack_format": [84, 0]}


def _project(tmp_path: Path, *, version: str = "26.1.2",
             profile: dict | None = None,
             evidence_formats: dict | None = None,
             sha1_verified: bool = True) -> Path:
    """Build a minimal project tree: profile always, evidence optionally."""
    root = tmp_path / "project"
    (root / "config" / "versions").mkdir(parents=True)
    (root / "build" / "compatibility").mkdir(parents=True)
    (root / "config" / "versions" / f"{version}.json").write_text(
        json.dumps({"formats": profile or PROFILE_FORMATS}), encoding="utf-8")
    if evidence_formats is not None:
        (root / "build" / "compatibility" / f"{version}.json").write_text(
            json.dumps({"id": version, "status": "metadata_found",
                        "support": "unverified",
                        "formats": evidence_formats,
                        "archive_evidence": {"server_sha1_verified": sha1_verified}}),
            encoding="utf-8")
    return root


def _datapack(tmp_path: Path) -> Path:
    root = tmp_path / "datapack"
    (root / "data" / "treehouse_village" / "function").mkdir(parents=True)
    (root / "pack.mcmeta").write_text(
        json.dumps({"pack": {"description": "test", "min_format": [101, 1],
                             "max_format": [101, 1]}}), encoding="utf-8")
    (root / "data" / "treehouse_village" / "function" / "help.mcfunction").write_text(
        "say help\n", encoding="utf-8")
    return root


def test_missing_profile_is_rejected(tmp_path):
    root = tmp_path / "project"
    (root / "build" / "compatibility").mkdir(parents=True)
    (root / "build" / "compatibility" / "9.9.9.json").write_text(
        json.dumps({"formats": PROFILE_FORMATS}), encoding="utf-8")
    with pytest.raises(ReleaseError, match="profile"):
        verify_release_evidence("9.9.9", root=root)


def test_missing_evidence_file_is_rejected(tmp_path):
    root = _project(tmp_path, evidence_formats=None)
    with pytest.raises(ReleaseError, match="evidence"):
        verify_release_evidence("26.1.2", root=root)


def test_evidence_format_mismatch_is_rejected(tmp_path):
    stale = dict(PROFILE_FORMATS, data_pack_format=[99, 0])
    root = _project(tmp_path, evidence_formats=stale)
    with pytest.raises(ReleaseError, match="formats"):
        verify_release_evidence("26.1.2", root=root)


def test_unverified_sha1_is_rejected(tmp_path):
    root = _project(tmp_path, evidence_formats=PROFILE_FORMATS,
                    sha1_verified=False)
    with pytest.raises(ReleaseError, match="sha1"):
        verify_release_evidence("26.1.2", root=root)


def test_matching_evidence_passes(tmp_path):
    root = _project(tmp_path, evidence_formats=PROFILE_FORMATS)
    evidence = verify_release_evidence("26.1.2", root=root)
    assert evidence["archive_evidence"]["server_sha1_verified"] is True
    assert evidence["formats"]["data_version"] == 4790


def test_zip_places_pack_mcmeta_at_archive_root(tmp_path):
    datapack = _datapack(tmp_path)
    archive = tmp_path / "out" / "treehouse-village-26.1.2.zip"
    build_release_zip(datapack, archive)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert "pack.mcmeta" in names
    # S11: never a wrapping folder — every entry lives at the datapack root.
    assert all("/pack.mcmeta" not in name for name in names)
    assert "data/treehouse_village/function/help.mcfunction" in names


def test_zip_rejects_datapack_without_pack_mcmeta(tmp_path):
    broken = tmp_path / "broken"
    (broken / "data").mkdir(parents=True)
    with pytest.raises(ReleaseError, match="pack.mcmeta"):
        build_release_zip(broken, tmp_path / "out" / "x.zip")


def test_checksums_line_matches_sha256_and_is_idempotent(tmp_path):
    datapack = _datapack(tmp_path)
    archive = tmp_path / "out" / "treehouse-village-26.1.2.zip"
    build_release_zip(datapack, archive)
    checksums = tmp_path / "out" / "SHA256SUMS.txt"
    update_checksums(archive, checksums)
    expected = f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}"
    assert checksums.read_text(encoding="utf-8").splitlines() == [expected]
    # Rebuild: the line must be replaced, not duplicated.
    update_checksums(archive, checksums)
    assert checksums.read_text(encoding="utf-8").splitlines() == [expected]
