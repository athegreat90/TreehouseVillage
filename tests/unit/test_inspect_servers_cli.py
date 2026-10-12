"""Public inspection command: help and rejected arguments do not download/write."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def invoke(*args):
    return subprocess.run([sys.executable, "scripts/inspect_servers.py", *args],
        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=10)


def snapshots():
    return {p.relative_to(ROOT).as_posix(): p.read_bytes()
            for folder in ("config/versions", "build/compatibility", "build/server-cache")
            for p in (ROOT / folder).glob("*") if p.is_file()}


def test_help():
    result = invoke("--help")
    assert result.returncode == 0
    assert "never launch Java" in result.stdout
    assert "26.1.2, 26.2, 26.3" in result.stdout
    assert "--timeout" in result.stdout
    assert result.stderr == ""


def test_rejected_target_does_not_write():
    before = snapshots()
    result = invoke("../escape")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.endswith("error: versions must be unique exact supported target IDs\n")
    assert snapshots() == before


def test_rejected_timeout_does_not_write():
    before = snapshots()
    result = invoke("--timeout", "0")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.endswith("error: timeout must be greater than 0 and at most 300 seconds\n")
    assert snapshots() == before
