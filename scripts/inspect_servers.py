"""Download verified official servers and record embedded formats; never launch Java."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treehouse_village.compatibility import (  # noqa: E402
    CompatibilityError, DEFAULT_TARGETS, EVIDENCE_DIR, PROFILE_DIR,
    discover, fetch_bytes, profile_from_record, write_json_atomic,
)
from treehouse_village.server_archive import MAX_ARCHIVE_BYTES, inspect_archive  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versions", nargs="*", choices=None,
                        help="Exact release IDs: 26.1.2, 26.2, 26.3 (default: all).")
    parser.add_argument("--timeout", type=float, default=30,
                        help="Network socket timeout in seconds (default: 30). No retries.")
    args = parser.parse_args(argv)
    targets = tuple(args.versions or DEFAULT_TARGETS)
    if any(v not in DEFAULT_TARGETS for v in targets) or len(set(targets)) != len(targets):
        parser.error("versions must be unique exact supported target IDs")
    if not 0 < args.timeout <= 300:
        parser.error("timeout must be greater than 0 and at most 300 seconds")
    cache = (ROOT / "build/server-cache").resolve()
    if ROOT not in cache.parents:
        parser.error("server cache resolves outside the project")
    report = {"ok": True, "targets": {}}
    try:
        records = discover(targets, timeout=args.timeout)
        for version, record in records.items():
            if record["status"] != "metadata_found" or record["official_type"] != "release":
                raise CompatibilityError(f"exact release unavailable: {version}")
            descriptor = record["server"]
            if descriptor["size"] > MAX_ARCHIVE_BYTES:
                raise CompatibilityError(f"server archive exceeds size limit: {version}")
            destination = cache / f"{version}-{descriptor['sha1']}.jar"
            if destination.exists():
                if destination.is_symlink() or destination.stat().st_size > MAX_ARCHIVE_BYTES:
                    raise CompatibilityError(f"unsafe cached server: {version}")
                print(f"Using cached official server {version}", flush=True)
                raw = destination.read_bytes()
            else:
                print(f"Downloading official server {version} ({descriptor['size']} bytes)", flush=True)
                raw = fetch_bytes(descriptor["url"], timeout=args.timeout, max_bytes=descriptor["size"])
            evidence = inspect_archive(raw, record)
            if not destination.exists():
                cache.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=cache, suffix=".part")
                try:
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(raw)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, destination)
                finally:
                    Path(temporary).unlink(missing_ok=True)
            record["formats"] = evidence["formats"]
            record["archive_evidence"] = evidence
            record["archive_path"] = destination.relative_to(ROOT).as_posix()
            write_json_atomic(ROOT, EVIDENCE_DIR, version, record)
            write_json_atomic(ROOT, PROFILE_DIR, version, profile_from_record(record))
            report["targets"][version] = {"formats": evidence["formats"], "archive": record["archive_path"]}
            print(f"Verified {version}: {json.dumps(evidence['formats'], sort_keys=True)}", flush=True)
    except (CompatibilityError, OSError) as exc:
        report["ok"] = False
        report["error"] = str(exc)
        print(f"Server inspection failed: {exc}", file=sys.stderr)
    write_json_atomic(ROOT, EVIDENCE_DIR, "server-inspection", report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
