"""Build version-labeled release ZIPs with checksums (S11, S12).

Pipeline per exact target version:
  1. verify_release_evidence gates the artifact on tracked compatibility
     evidence (profile formats match + verified server sha1);
  2. build_datapack regenerates the datapack (both villages + functions)
     pinned to that version's profile into build/release/<version>/;
  3. build_release_zip archives it with pack.mcmeta at the archive root;
  4. update_checksums refreshes dist/SHA256SUMS.txt.

Nothing here certifies in-game village support: evidence carries
support=unverified and runtime_qa=pending, disclosed in the release docs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treehouse_village.config import CompactConfig, MegaConfig  # noqa: E402
from treehouse_village.datapack import build_datapack  # noqa: E402
from treehouse_village.packaging import (ReleaseError, build_release_zip,  # noqa: E402
                                         update_checksums,
                                         verify_release_evidence)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = ("26.1.2", "26.2", "26.3")


def build_release(root: Path, version: str) -> tuple[Path, Path]:
    """Evidence-gated datapack build + ZIP + checksums for one version."""
    verify_release_evidence(version, root=root)
    configs = {
        "compact": CompactConfig.from_json(root / "config" / "compact.json"),
        "mega": MegaConfig.from_json(root / "config" / "mega.json"),
    }
    staging = root / "build" / "release" / version
    build_datapack(configs, version=version, out=staging)
    archive = build_release_zip(staging, root / "dist" / f"treehouse-village-{version}.zip")
    checksums = update_checksums(archive, root / "dist" / "SHA256SUMS.txt")
    return archive, checksums


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versions", nargs="*",
                        help="Exact targets: 26.1.2, 26.2, 26.3 (default: all).")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="project root receiving config/, build/ and dist/")
    args = parser.parse_args(argv)
    targets = tuple(args.versions or DEFAULT_TARGETS)
    if any(v not in DEFAULT_TARGETS for v in targets) or len(set(targets)) != len(targets):
        parser.error("versions must be unique exact supported target IDs")
    for version in targets:
        try:
            archive, checksums = build_release(args.root, version)
        except ReleaseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"{version}: {archive.relative_to(args.root)} + {checksums.relative_to(args.root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
