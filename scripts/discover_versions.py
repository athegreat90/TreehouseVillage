#!/usr/bin/env python3
"""Discover Mojang metadata for the target Minecraft versions (see docs/compatibility)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from treehouse_village import compatibility as c  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("targets", nargs="*", default=list(c.DEFAULT_TARGETS), help="exact version ids (default: %(default)s)")
    p.add_argument("--timeout", type=float, default=c.DEFAULT_TIMEOUT, help="per-request timeout in seconds (default: %(default)s)")
    p.add_argument("--root", type=Path, default=ROOT, help="project root receiving build/compatibility and config/versions")
    args = p.parse_args(argv)
    try:
        report = c.run(args.root, args.targets, timeout=args.timeout)
    except c.CompatibilityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if "error" in report:
        print(f"error: {report['error']}", file=sys.stderr)
    for target, info in report["targets"].items():
        print(f"{target}: {info['outcome']}" + (f" ({info['error']})" if "error" in info else ""))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
