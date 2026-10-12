"""Isolated public smoke-harness tests; fake consoles are not Minecraft QA."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from treehouse_village.server_smoke import prepare_probe, run_console


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/smoke_servers.py"


def _project(root, version="26.1.2", data_version=4790,
             data_format=(101, 1), resource_format=(84, 0)):
    (root / "config/versions").mkdir(parents=True)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("version.json", json.dumps({
            "id": version, "world_version": data_version,
            "pack_version": {"data_major": data_format[0], "data_minor": data_format[1],
                             "resource_major": resource_format[0], "resource_minor": resource_format[1]},
        }))
    raw = archive.getvalue()
    cache = root / "build/server-cache"
    cache.mkdir(parents=True)
    jar = cache / "fixture.jar"
    jar.write_bytes(raw)
    profile = {
        "id": version, "archive_path": "build/server-cache/fixture.jar",
        "server": {"size": len(raw), "sha1": hashlib.sha1(raw).hexdigest()},
        "formats": {"data_version": data_version, "data_pack_format": list(data_format),
                    "resource_pack_format": list(resource_format)},
    }
    (root / "config/versions" / f"{version}.json").write_text(json.dumps(profile))
    return profile


def _snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_rejected_eula_leaves_project_unchanged(tmp_path):
    _project(tmp_path)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="explicit --accept-eula"):
        prepare_probe(tmp_path, "26.1.2", accept_eula=False)
    assert _snapshot(tmp_path) == before


def test_26_3_preparation_uses_lowercase_palette_schema(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("p")
    _project(tmp_path, version="26.3", data_version=5023, data_format=(121, 0), resource_format=(97, 1))
    probe = prepare_probe(tmp_path, "26.3", accept_eula=True)
    from rapidnbt import nbtio
    root = nbtio.load(probe.directory / "world/datapacks/treehouse_village_probe/data/treehouse_village_probe/structure/probe.nbt")
    palette = root["palette"]
    assert "id" in palette[0]
    assert "properties" in palette[0]
    assert palette[0]["id"].value == b"minecraft:jungle_log"
    assert palette[0]["properties"]["axis"].value == b"y"
    assert "id" in palette[1]
    assert "properties" in palette[1]
    assert palette[1]["id"].value == b"minecraft:lantern"
    assert palette[1]["properties"]["hanging"].value == b"false"


def test_preparation_has_real_gzip_structure_and_exact_metadata(tmp_path_factory):
    # Keep the nested synthetic project below legacy Windows path limits.
    tmp_path = tmp_path_factory.mktemp("p")
    _project(tmp_path)
    probe = prepare_probe(tmp_path, "26.1.2", accept_eula=True)
    pack = probe.directory / "world/datapacks/treehouse_village_probe"
    metadata = json.loads((pack / "pack.mcmeta").read_text())
    assert metadata["pack"]["min_format"] == [101, 1]
    assert metadata["pack"]["max_format"] == [101, 1]
    nbt = pack / "data/treehouse_village_probe/structure/probe.nbt"
    assert nbt.read_bytes()[:2] == b"\x1f\x8b"
    assert gzip.decompress(nbt.read_bytes())[:3] == b"\x0a\x00\x00"
    assert (probe.directory / "eula.txt").read_text() == "eula=true\n"
    commands = (pack / "data/treehouse_village_probe/function/check.mcfunction").read_text()
    assert "place template treehouse_village_probe:probe 0 100 0\n" in commands
    assert "if block 0 100 0 minecraft:jungle_log[axis=y]" in commands
    assert "if block 0 101 0 minecraft:lantern[hanging=false,waterlogged=false]" in commands
    assert commands.endswith(f"run say {probe.token}\n")
    properties = (probe.directory / "server.properties").read_text()
    assert "server-ip=127.0.0.1\n" in properties
    assert "server-port=0\n" in properties
    assert "enable-rcon=false\n" in properties
    assert "online-mode=true\n" in properties
    second = prepare_probe(tmp_path, "26.1.2", accept_eula=True)
    assert second.directory != probe.directory
    assert second.token != probe.token


def test_tampered_archive_is_rejected_without_new_artifacts(tmp_path):
    _project(tmp_path)
    (tmp_path / "build/server-cache/fixture.jar").write_bytes(b"not verified")
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="size mismatch"):
        prepare_probe(tmp_path, "26.1.2", accept_eula=True)
    assert _snapshot(tmp_path) == before


def test_profile_archive_escape_is_rejected_without_new_artifacts(tmp_path):
    profile = _project(tmp_path)
    profile["archive_path"] = "../outside.jar"
    (tmp_path / "config/versions/26.1.2.json").write_text(json.dumps(profile))
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="outside the project"):
        prepare_probe(tmp_path, "26.1.2", accept_eula=True)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("prefix", ["", "[Server] ", "[Not Secure] [Server] "])
def test_console_requires_placement_signal_then_clean_shutdown(tmp_path, prefix):
    token = "TV_NBT_PROBE_PASS_test"
    code = (
        "import sys\n"
        "print('[00:00:00] [Server thread/INFO]: Done (0.1s)! For help, type help',flush=True)\n"
        "assert input() == 'function treehouse_village_probe:check'\n"
        f"print('[00:00:00] [Server thread/INFO]: {prefix}{token}',flush=True)\n"
        "assert input() == 'stop'\n"
    )
    result = run_console([sys.executable, "-u", "-c", code], tmp_path, token, timeout=5)
    assert result == {"passed": True, "exit_code": 0}
    log = (tmp_path / "server-console.log").read_text()
    assert token in log
    assert "Traceback" not in log


def test_console_accepts_26_3_system_chat_prefix(tmp_path):
    token = "TV_NBT_PROBE_PASS_test"
    code = (
        "print('[00:00:00] [Server thread/INFO]: Done (0.1s)!',flush=True)\n"
        "assert input() == 'function treehouse_village_probe:check'\n"
        f"print('[00:00:00] [Server thread/INFO]: System chat: [Not Secure] [Server] {token}',flush=True)\n"
        "assert input() == 'stop'\n"
    )
    result = run_console([sys.executable, "-u", "-c", code], tmp_path, token, timeout=5)
    assert result == {"passed": True, "exit_code": 0}


def test_console_rejects_token_without_server_log_prefix(tmp_path):
    token = "TV_NBT_PROBE_PASS_test"
    code = f"print('{token}',flush=True)"
    result = run_console([sys.executable, "-u", "-c", code], tmp_path, token, timeout=5)
    assert result == {"passed": False, "exit_code": 0}


def test_console_timeout_stops_child_and_does_not_pass(tmp_path):
    result = run_console([sys.executable, "-u", "-c", "input()"], tmp_path,
                         "TV_NBT_PROBE_PASS_test", timeout=0.2)
    assert result["passed"] is False
    assert result["timed_out"] is True
    assert result["exit_code"] != 0


def test_cli_requires_eula_before_writing_worlds():
    result = subprocess.run([sys.executable, "-B", str(CLI), "26.1.2"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.endswith("error: explicit --accept-eula is required to create and launch a test server\n")


def test_cli_help_documents_isolated_worlds_and_eula():
    result = subprocess.run([sys.executable, "-B", str(CLI), "--help"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stderr == ""
    assert "--accept-eula" in result.stdout
    assert "build/worlds/nbt-smoke" in result.stdout
    assert "not certify village compatibility" in result.stdout
