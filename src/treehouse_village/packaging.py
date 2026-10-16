"""Evidence-gated release packaging: version ZIPs + checksums (S11, S12).

The offline tooling never claims a version it cannot justify: before any
version-labeled artifact is produced, `verify_release_evidence` requires
the tracked compatibility evidence to exist for that version, to match
the verified profile formats in `config/versions/<v>.json`, and to record
a verified server sha1. `build_release_zip` then archives a built
datapack directory with `pack.mcmeta` at the archive root — never inside
an extra wrapping folder (S11). `update_checksums` maintains a standard
`SHA256SUMS.txt` (`<sha256>  <filename>` per line) and replaces a line on
rebuild instead of duplicating it (S12).

Pure JSON/zip work: no Minecraft run is claimed here; `support=unverified`
in the evidence only discloses what the release notes already say.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


class ReleaseError(ValueError):
    """A release precondition failed (missing/mismatched evidence or pack)."""


def verify_release_evidence(version: str, *, root: Path) -> dict:
    """Gate a version-labeled artifact on its compatibility evidence.

    Requires, in order: the verified profile (`config/versions/<v>.json`),
    the tracked evidence (`build/compatibility/<v>.json`), evidence formats
    identical to the profile formats, and `archive_evidence.server_sha1_verified
    is True`. Returns the parsed evidence for reuse by callers.
    """
    profile_path = root / "config" / "versions" / f"{version}.json"
    if not profile_path.is_file():
        raise ReleaseError(f"no verified profile for {version}: {profile_path}")
    evidence_path = root / "build" / "compatibility" / f"{version}.json"
    if not evidence_path.is_file():
        raise ReleaseError(
            f"no compatibility evidence for {version}: {evidence_path}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))["formats"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_formats = evidence.get("formats") or {}
    for key in ("data_pack_format", "data_version"):
        if evidence_formats.get(key) != profile.get(key):
            raise ReleaseError(
                f"evidence formats for {version} do not match the verified "
                f"profile ({key}: {evidence_formats.get(key)!r} != {profile.get(key)!r})")
    archive_evidence = evidence.get("archive_evidence") or {}
    if archive_evidence.get("server_sha1_verified") is not True:
        raise ReleaseError(
            f"compatibility evidence for {version} lacks a verified server sha1")
    return evidence


def build_release_zip(datapack_dir: Path, archive: Path) -> Path:
    """Zip `datapack_dir` with `pack.mcmeta` at the archive root (S11).

    Refuses a directory without a root `pack.mcmeta` and re-opens the
    finished zip to prove no wrapping folder crept in.
    """
    datapack_dir = Path(datapack_dir)
    archive = Path(archive)
    if not (datapack_dir / "pack.mcmeta").is_file():
        raise ReleaseError(
            f"datapack has no pack.mcmeta at its root: {datapack_dir}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(datapack_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(datapack_dir).as_posix())
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    if "pack.mcmeta" not in names:
        raise ReleaseError(f"archive lost its root pack.mcmeta: {archive}")
    if any(name.endswith("/pack.mcmeta") for name in names):
        raise ReleaseError(
            f"pack.mcmeta sits inside a wrapping folder: {archive}")
    return archive


def update_checksums(archive: Path, checksums: Path) -> Path:
    """Write/refresh this archive's `<sha256>  <filename>` line (S12)."""
    archive = Path(archive)
    checksums = Path(checksums)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    line = f"{digest}  {archive.name}"
    lines: list[str] = []
    if checksums.is_file():
        lines = [entry for entry in checksums.read_text(encoding="utf-8").splitlines()
                 if entry and not entry.endswith(f"  {archive.name}")]
    lines.append(line)
    lines.sort()
    checksums.parent.mkdir(parents=True, exist_ok=True)
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums
