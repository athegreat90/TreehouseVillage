"""Load a two-block NBT probe on exact vanilla servers in disposable worlds.

All worlds/logs stay under build/worlds/nbt-smoke. This does not certify village compatibility.
Accepting the Minecraft EULA is an explicit prerequisite; no automatic acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treehouse_village.compatibility import DEFAULT_TARGETS  # noqa: E402
from treehouse_village.server_smoke import prepare_probe, run_probe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versions", nargs="*",
                        help="Exact targets: 26.1.2, 26.2, 26.3 (default: all).")
    parser.add_argument("--accept-eula", action="store_true",
                        help="Explicitly accept https://aka.ms/MinecraftEULA for isolated test servers.")
    parser.add_argument("--timeout", type=float, default=180,
                        help="Total deadline per server, including shutdown; 0 < seconds <= 900 (default: 180). No retries.")
    args = parser.parse_args(argv)
    if not args.accept_eula:
        parser.error("explicit --accept-eula is required to create and launch a test server")
    targets = tuple(args.versions or DEFAULT_TARGETS)
    if any(v not in DEFAULT_TARGETS for v in targets) or len(set(targets)) != len(targets):
        parser.error("versions must be unique exact supported target IDs")
    if not 0 < args.timeout <= 900:
        parser.error("timeout must be greater than 0 and at most 900 seconds")
    for version in targets:
        try:
            probe = prepare_probe(ROOT, version, accept_eula=args.accept_eula)
            print(f"Launching isolated NBT probe for {version}: {probe.directory}", flush=True)
            result = run_probe(probe, timeout=args.timeout)
        except (OSError, ValueError, KeyError) as exc:
            print(f"NBT smoke probe failed for {version}: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, sort_keys=True), flush=True)
        if not result["passed"]:
            print(f"NBT smoke probe failed for {version}; see server-console.log.", file=sys.stderr)
            return 1
    print("Exact-server two-block NBT probes passed; village support remains unverified.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
