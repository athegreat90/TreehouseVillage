"""T8: datapack assembly — verified-version metadata, NBT templates, placement lifecycle.

Every assertion is static over generated files: no Minecraft is launched. The
placement contract follows spec section 12/16: relative coordinates only, a
marker-carried build session, staged template placement, no gamerule/time/
weather/difficulty/forceload mutations outside the explicit sunset showcase.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from treehouse_village.config import CompactConfig, MegaConfig
from treehouse_village.datapack import SEGMENT_SIZE, build_datapack
from treehouse_village.village import generate_compact_village

ROOT = Path(__file__).resolve().parents[2]


def _profile(version: str) -> dict:
    data = json.loads((ROOT / "config" / "versions" / f"{version}.json").read_text(encoding="utf-8"))
    return data["formats"]


@pytest.fixture(scope="module")
def configs() -> dict:
    return {
        "compact": CompactConfig.from_json(ROOT / "config" / "compact.json"),
        "mega": MegaConfig.from_json(ROOT / "config" / "mega.json"),
    }


@pytest.fixture(scope="module")
def pack_263(tmp_path_factory, configs):
    out = tmp_path_factory.mktemp("t8_pack") / "datapack_263"
    return build_datapack(configs, version="26.3", out=out)


@pytest.fixture(scope="module")
def pack_262(tmp_path_factory, configs):
    out = tmp_path_factory.mktemp("t8_pack") / "datapack_262"
    return build_datapack(configs, version="26.2", out=out)


def _function_dir(pack) -> Path:
    return pack.out / "data" / "treehouse_village" / "function"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pack_mcmeta_matches_verified_version_profile(pack_263, pack_262):
    for pack, version in ((pack_263, "26.3"), (pack_262, "26.2")):
        raw = json.loads((pack.out / "pack.mcmeta").read_text(encoding="utf-8"))
        expected = _profile(version)["data_pack_format"]
        assert raw["pack"]["min_format"] == expected
        assert raw["pack"]["max_format"] == expected
        assert isinstance(raw["pack"]["description"], str) and raw["pack"]["description"]


def test_function_surface_covers_required_commands(pack_263):
    base = _function_dir(pack_263)
    required = [
        "help.mcfunction", "preview.mcfunction", "status.mcfunction",
        "cleanup.mcfunction", "showcase/sunset.mcfunction",
        "place/mega.mcfunction", "place/mega_force.mcfunction",
        "place/compact.mcfunction", "place/compact_force.mcfunction",
        "place/mega_begin.mcfunction", "place/mega_check.mcfunction",
        "place/mega_reject.mcfunction", "place/mega_done.mcfunction",
        "place/mega_failed.mcfunction",
    ]
    for rel in required:
        assert (base / rel).is_file(), f"missing function {rel}"
    for variant in ("mega", "compact"):
        ticks = list((base / "place").glob(f"{variant}_tick*.mcfunction"))
        assert ticks, f"no staged tick functions for {variant}"


def test_place_avoids_forbidden_world_mutations(pack_263):
    base = _function_dir(pack_263)
    forbidden = ("gamerule", "time set", "weather", "difficulty", "forceload",
                 "teleport", re.compile(r"(^|\s)tp(\s|$)"))
    sunset = base / "showcase" / "sunset.mcfunction"
    for path in base.rglob("*.mcfunction"):
        text = _read(path)
        if path == sunset:
            assert "time set sunset" in text
            continue
        for token in forbidden:
            pattern = token if isinstance(token, re.Pattern) else re.escape(token)
            assert not re.search(pattern, text), f"{path.name} contains forbidden {token!r}"
    assert "time set" in _read(sunset)
    # exactly one file anywhere may set time
    setters = [p for p in base.rglob("*.mcfunction") if "time set" in _read(p)]
    assert setters == [sunset]


def test_place_entry_guards_busy_session_and_dimension(pack_263):
    base = _function_dir(pack_263) / "place"
    for variant in ("mega", "compact"):
        entry = _read(base / f"{variant}.mcfunction")
        assert "if entity @e[type=marker,tag=tv_origin]" in entry
        assert f"function treehouse_village:place/{variant}_begin" in entry
        begin = _read(base / f"{variant}_begin.mcfunction")
        assert "if dimension minecraft:overworld" in begin
        assert "unless dimension minecraft:overworld" in begin
        force = _read(base / f"{variant}_force.mcfunction")
        assert "summon minecraft:marker" in force
        assert f"place/{variant}_check" not in force


def test_begin_summons_aligned_marker_and_check_samples_obstructions(pack_263):
    base = _function_dir(pack_263) / "place"
    for variant in ("mega", "compact"):
        begin = _read(base / f"{variant}_begin.mcfunction")
        assert "align xz run summon minecraft:marker" in begin
        assert 'Tags:["tv_origin"' in begin
        assert "data modify storage treehouse_village:session set value" in begin
        check = _read(base / f"{variant}_check.mcfunction")
        assert "unless block" in check
        assert "if entity @e[type=marker,tag=tv_origin]" in check
        assert f"function treehouse_village:place/{variant}_tick0" in check
        reject = _read(base / f"{variant}_reject.mcfunction")
        assert "kill @e[type=marker,tag=tv_origin]" in reject
        assert "tellraw" in reject


def test_staged_ticks_match_structures_and_use_relative_offsets(pack_263):
    from treehouse_village.serialization import segment_scene

    base = _function_dir(pack_263) / "place"
    for variant in ("mega", "compact"):
        n_structures = len(list(
            (pack_263.out / "data" / "treehouse_village" / "structure" / variant).glob("*.nbt")))
        assert n_structures >= 1
        tick_files = sorted(base.glob(f"{variant}_tick*.mcfunction"),
                            key=lambda p: int(re.search(r"tick(\d+)", p.name).group(1)))
        assert [int(re.search(r"tick(\d+)", p.name).group(1)) for p in tick_files] == list(
            range(n_structures)), f"{variant}: tick/structure count mismatch"
        for k, path in enumerate(tick_files):
            text = _read(path)
            match = re.search(
                rf"place template treehouse_village:{variant}/{k} ~(-?\d+) ~(-?\d+) ~(-?\d+)", text)
            assert match, f"{path.name}: relative place template missing"
            if k < n_structures - 1:
                assert (f"schedule function treehouse_village:place/{variant}_tick{k + 1} 1t replace"
                        in text), f"{path.name}: next stage not scheduled"
            else:
                assert "schedule" not in text, f"{path.name}: final stage must not reschedule"
                assert f"function treehouse_village:place/{variant}_done" in text
                assert f"function treehouse_village:place/{variant}_failed" in text
                assert "~10 ~0 ~10 minecraft:grass_block" in text
    # No template anywhere may bake an absolute world position.
    for path in (_function_dir(pack_263) / "place").rglob("*.mcfunction"):
        assert not re.search(r"place template \S+ -?\d+ -?\d+ -?\d+", _read(path)), path.name


def test_compact_offsets_match_serialization_segments(pack_263):
    from treehouse_village.serialization import segment_scene

    village = generate_compact_village(pack_263.configs["compact"] if hasattr(pack_263, "configs")
                                       else CompactConfig.from_json(ROOT / "config" / "compact.json"))
    segments = segment_scene(village.scene, max_size=SEGMENT_SIZE)
    expected = [seg.origin + seg.scene.bounds.minimum for seg in segments]
    tick_files = sorted((_function_dir(pack_263) / "place").glob("compact_tick*.mcfunction"),
                        key=lambda p: int(re.search(r"tick(\d+)", p.name).group(1)))
    assert len(tick_files) == len(expected)
    observed = []
    for path in tick_files:
        match = re.search(r"place template treehouse_village:compact/\d+ ~(-?\d+) ~(-?\d+) ~(-?\d+)",
                          _read(path))
        assert match, path.name
        observed.append(tuple(int(g) for g in match.groups()))
    # Vec3 is a plain frozen dataclass (no __iter__); compare components.
    assert observed == [(offset.x, offset.y, offset.z) for offset in expected]


def test_structure_templates_are_valid_gzip_nbt(pack_263, pack_262):
    from rapidnbt import nbtio

    for pack, version in ((pack_263, "26.3"), (pack_262, "26.2")):
        formats = _profile(version)
        data_version = formats["data_version"]
        # 26.3 (DataVersion 5023+) uses the modern id/properties palette keys;
        # earlier verified targets use the legacy Name/Properties keys.
        modern = data_version >= 5023
        for variant in ("compact", "mega"):
            files = sorted(
                (pack.out / "data" / "treehouse_village" / "structure" / variant).glob("*.nbt"),
                key=lambda p: int(p.stem))
            assert files, f"{variant}: no structure templates"
            for path in files:
                raw = path.read_bytes()
                assert raw[:2] == b"\x1f\x8b", path
                root = nbtio.loads(raw)
                assert int(root["DataVersion"]) == data_version
                size = [int(child) for child in root["size"]]
                assert len(size) == 3 and all(value > 0 for value in size)
                palette = root["palette"]
                blocks = root["blocks"]
                assert len(palette) >= 1 and len(blocks) >= 1
                import gzip
                decoded = gzip.decompress(raw)
                if modern:
                    assert b"\x00\x02id" in decoded and b"\x00\x04Name" not in decoded
                else:
                    assert b"\x00\x04Name" in decoded and b"\x00\x02id" not in decoded
                for block in blocks:
                    state = int(block["state"])
                    assert 0 <= state < len(palette)
                    pos = [int(component) for component in block["pos"]]
                    assert len(pos) == 3
                    assert all(0 <= pos[i] < size[i] for i in range(3)), f"{path}: {pos} vs {size}"


def test_status_cleanup_reports_and_help_documents(pack_263):
    base = _function_dir(pack_263)
    status = _read(base / "status.mcfunction")
    assert "if entity @e[type=marker,tag=tv_origin]" in status
    assert "data get storage treehouse_village:session" in status
    assert "data get entity @e[type=marker,tag=tv_origin,limit=1] Pos" in status
    assert "unless entity @e[type=marker,tag=tv_origin]" in status
    cleanup = _read(base / "cleanup.mcfunction")
    assert "kill @e[type=marker,tag=tv_origin]" in cleanup
    assert "data modify storage treehouse_village:session set value" in cleanup
    for variant in ("mega", "compact"):
        assert "tellraw" in _read(base / "place" / f"{variant}_done.mcfunction")
        assert "kill @e[type=marker,tag=tv_origin]" in _read(base / "place" / f"{variant}_done.mcfunction")
        failed = _read(base / "place" / f"{variant}_failed.mcfunction")
        assert "tellraw" in failed and "kill @e[type=marker,tag=tv_origin]" in failed
    help_text = _read(base / "help.mcfunction")
    for command in ("place/mega", "place/compact", "place/mega_force", "place/compact_force",
                    "preview", "status", "cleanup", "showcase/sunset"):
        assert command in help_text, f"help does not document {command}"


def test_preview_draws_only_particles(pack_263):
    text = _read(_function_dir(pack_263) / "preview.mcfunction")
    assert "particle minecraft:electric_spark" in text
    for forbidden in ("fill ", "setblock", "worldborder", "summon"):
        assert forbidden not in text
