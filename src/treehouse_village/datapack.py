"""Datapack assembly: verified-version metadata, segmented NBT templates, staged placement.

`build_datapack` turns declarative village configurations into a vanilla
datapack tree:

- ``pack.mcmeta`` pinned to one verified version profile (min/max format
  arrays exactly as the smoke-verified probe datapack used);
- gzip-compressed structure templates segmented at :data:`SEGMENT_SIZE`,
  one file per segment under ``data/<ns>/structure/<variant>/``;
- the placement lifecycle functions from spec sections 12/16: a
  marker-carried build session, one ``place template`` per tick chained
  with ``schedule``, an obstruction probe with a documented force mode,
  status/cleanup over the marker + session storage, and an explicitly
  invoked sunset showcase.

Placement functions never bake absolute world coordinates: templates use
``~`` offsets relative to the summoned session marker, which itself is
aligned to the block the player stands on.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from shutil import rmtree
import re
from typing import Mapping

from .config import VillageConfig
from .geometry.model import Vec3
from .serialization import StructureSerializer, segment_scene
from .village import generate_village

SEGMENT_SIZE = Vec3(48, 32, 48)
"""Maximum structure-template box and the staging granularity (one per tick)."""

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_VARIANT_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True)
class Datapack:
    """A generated datapack tree on disk."""

    out: Path
    version: str
    configs: Mapping[str, VillageConfig]
    structures: tuple[Path, ...]
    functions: tuple[Path, ...]


def _load_profile(version: str) -> dict:
    path = _PROJECT_ROOT / "config" / "versions" / f"{version}.json"
    if not path.is_file():
        raise ValueError(f"unknown or unverified Minecraft version: {version}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        formats = data["formats"]
        pack_format = formats["data_pack_format"]
        data_version = formats["data_version"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"invalid version profile for {version}: {error}") from error
    if (not isinstance(pack_format, list) or len(pack_format) != 2
            or not all(isinstance(part, int) for part in pack_format)):
        raise ValueError(f"version profile {version} lacks a verified data_pack_format")
    if not isinstance(data_version, int) or data_version < 0:
        raise ValueError(f"version profile {version} lacks a verified data_version")
    return {"data_pack_format": pack_format, "data_version": data_version}


def _write_function(root: Path, relative: str, lines: list[str]) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def _tellraw(target: str, text: str, color: str) -> str:
    return (f'tellraw {target} [{{"text": {json.dumps(text)}, '
            f'"color": "{color}"}}]')


def _busy_text(variant: str) -> str:
    return (f"A build session is already active. Run /function "
            f"treehouse_village:status or /function treehouse_village:cleanup first "
            f"before placing the {variant} village.")


def _shared_function_lines(name: str, configs: Mapping[str, VillageConfig]) -> list[str]:
    if name == "help":
        lines = [
            _tellraw("@s", "Ultimate Treehouse Village - placement help", "gold"),
            _tellraw("@s", "Stand on the full block at the village origin "
                           "(south-west bottom corner) first.", "gray"),
            _tellraw("@s", "Preview footprints: /function treehouse_village:preview", "aqua"),
        ]
        for variant in configs:
            lines.append(_tellraw(
                "@s", f"Place {variant}: /function treehouse_village:place/{variant} "
                      f"(force: /function treehouse_village:place/{variant}_force)", "aqua"))
        lines += [
            _tellraw("@s", "Session status: /function treehouse_village:status", "aqua"),
            _tellraw("@s", "Clear the session: /function treehouse_village:cleanup", "aqua"),
            _tellraw("@s", "Sunset showcase: /function treehouse_village:showcase/sunset", "aqua"),
        ]
        return lines
    if name == "preview":
        lines = ["# Outline each variant footprint from your position (spec section 12)."]
        for config in configs.values():
            width, depth = config.width, config.depth
            lines += [
                f"particle minecraft:electric_spark ~ ~1 ~ {width - 1} 0 0 0 60",
                f"particle minecraft:electric_spark ~ ~1 ~{depth - 1} {width - 1} 0 0 0 60",
                f"particle minecraft:electric_spark ~ ~1 ~ 0 0 {depth - 1} 0 60",
                f"particle minecraft:electric_spark ~{width - 1} ~1 ~ 0 0 {depth - 1} 0 60",
            ]
        lines.append(_tellraw(
            "@s", "Outlined the village footprints relative to your position.", "aqua"))
        return lines
    if name == "status":
        return [
            "# Report the active build session: state, marker identity, origin (spec section 16).",
            "execute if entity @e[type=marker,tag=tv_origin] run data get storage treehouse_village:session",
            "execute if entity @e[type=marker,tag=tv_origin] run data get entity "
            "@e[type=marker,tag=tv_origin,limit=1] UUID",
            "execute if entity @e[type=marker,tag=tv_origin] run data get entity "
            "@e[type=marker,tag=tv_origin,limit=1] Pos",
            "execute unless entity @e[type=marker,tag=tv_origin] run " +
            _tellraw("@s", "No active build session.", "gray"),
        ]
    if name == "cleanup":
        return [
            "# Clear the session marker without touching placed structures (spec sections 12/16).",
            "kill @e[type=marker,tag=tv_origin]",
            'data modify storage treehouse_village:session set value {"variant":"none","stage":-1}',
            _tellraw("@s", "Build session cleared. Run placement again when the site is ready.",
                     "gray"),
        ]
    if name == "showcase/sunset":
        return [
            "# Explicitly invoked sunset showcase only (spec section 11).",
            "time set sunset",
            _tellraw("@s", "Sunset showcase: enjoy the village at sunset.", "gold"),
        ]
    raise ValueError(f"unknown shared function: {name}")


def _variant_function_lines(variant: str, name: str, width: int, depth: int,
                            total: int, offsets: list[Vec3], k: int | None = None) -> list[str]:
    overworld_error = f"The {variant} village can only be placed in the Overworld."
    session_start = f'{{"variant":"{variant}","stage":0}}'
    marker = f"Tags:[\"tv_origin\",\"tv_{variant}\"]"
    gated = f"if entity @e[type=marker,tag=tv_origin,tag=tv_{variant}]"
    if name == "entry":
        return [
            f"# Place the {variant} village from your position (spec section 12).",
            "execute if entity @e[type=marker,tag=tv_origin] run " +
            _tellraw("@s", _busy_text(variant), "red"),
            f"execute unless entity @e[type=marker,tag=tv_origin] run "
            f"function treehouse_village:place/{variant}_begin",
        ]
    if name == "begin":
        return [
            "# Capture the origin, validate the dimension, record the session, then probe.",
            "execute unless dimension minecraft:overworld run " +
            _tellraw("@s", overworld_error, "red"),
            f"execute if dimension minecraft:overworld run data modify storage "
            f"treehouse_village:session set value {session_start}",
            f"execute if dimension minecraft:overworld align xz run summon minecraft:marker "
            f"~ ~-1 ~ {marker}",
            f"execute if dimension minecraft:overworld run function "
            f"treehouse_village:place/{variant}_check",
        ]
    if name == "check":
        inset = 10
        probes = [
            (inset, inset),
            (width - 1 - inset, inset),
            (inset, depth - 1 - inset),
            (width - 1 - inset, depth - 1 - inset),
            (width // 2, depth // 2),
        ]
        lines = ["# Probe the site for existing blocks before placing (spec section 12)."]
        for x, z in probes:
            lines.append(
                "execute if entity @e[type=marker,tag=tv_origin] at "
                "@e[type=marker,tag=tv_origin,limit=1] unless block "
                f"~{x} ~1 ~{z} minecraft:air run function "
                f"treehouse_village:place/{variant}_reject")
        lines.append(
            "execute if entity @e[type=marker,tag=tv_origin] run function "
            f"treehouse_village:place/{variant}_tick0")
        return lines
    if name == "reject":
        return [
            "# Abort the session when the probe finds existing blocks (spec section 12).",
            _tellraw("@s", f"Placement rejected: the {variant} site is not clear. "
                           "Clear the probed cells or use the documented force function.",
                     "red"),
            'data modify storage treehouse_village:session set value '
            '{"variant":"none","stage":-2}',
            "kill @e[type=marker,tag=tv_origin]",
        ]
    if name == "force":
        return [
            "# Explicit force mode: skip the obstruction probe (spec section 12).",
            "execute if entity @e[type=marker,tag=tv_origin] run " +
            _tellraw("@s", _busy_text(variant), "red"),
            f"execute unless entity @e[type=marker,tag=tv_origin] run data modify storage "
            f"treehouse_village:session set value {session_start}",
            "execute unless dimension minecraft:overworld run " +
            _tellraw("@s", overworld_error, "red"),
            f"execute unless entity @e[type=marker,tag=tv_origin] run execute if dimension "
            f"minecraft:overworld run schedule function "
            f"treehouse_village:place/{variant}_tick0 1t replace",
            f"execute unless entity @e[type=marker,tag=tv_origin] run execute if dimension "
            f"minecraft:overworld align xz run summon minecraft:marker ~ ~-1 ~ {marker}",
        ]
    if name == "done":
        return [
            _tellraw("@a", f"The {variant} village was placed successfully. Run "
                           "/function treehouse_village:cleanup to clear the session marker.",
                     "green"),
            f'data modify storage treehouse_village:session set value '
            f'{{"variant":"{variant}","stage":-1}}',
            "kill @e[type=marker,tag=tv_origin]",
        ]
    if name == "failed":
        return [
            _tellraw("@a", f"The {variant} village placement FAILED verification: the "
                           "ground plane was not placed. Run /function "
                           "treehouse_village:cleanup, clear the site, then retry.", "red"),
            f'data modify storage treehouse_village:session set value '
            f'{{"variant":"{variant}","stage":-2}}',
            "kill @e[type=marker,tag=tv_origin]",
        ]
    if name == "tick" and k is not None:
        offset = offsets[k]
        lines = [
            f"# Place segment {k + 1} of {total} while this session marker exists "
            f"(spec sections 12/16).",
            f"execute {gated} at @e[type=marker,tag=tv_origin,limit=1] run "
            f"place template treehouse_village:{variant}/{k} "
            f"~{offset.x} ~{offset.y} ~{offset.z}",
        ]
        if k < total - 1:
            lines += [
                f"execute {gated} run data modify storage treehouse_village:session set value "
                f'{{"variant":"{variant}","stage":{k + 1}}}',
                f"execute {gated} run schedule function "
                f"treehouse_village:place/{variant}_tick{k + 1} 1t replace",
            ]
        else:
            lines += [
                f"execute {gated} at @e[type=marker,tag=tv_origin,limit=1] if block "
                f"~10 ~0 ~10 minecraft:grass_block run function "
                f"treehouse_village:place/{variant}_done",
                f"execute {gated} at @e[type=marker,tag=tv_origin,limit=1] unless block "
                f"~10 ~0 ~10 minecraft:grass_block run function "
                f"treehouse_village:place/{variant}_failed",
            ]
        return lines
    raise ValueError(f"unknown variant function: {name}")


def build_datapack(configs: Mapping[str, VillageConfig], *, version: str,
                   out: Path | str) -> Datapack:
    """Generate a datapack tree for ``configs`` pinned to ``version``.

    The output directory is regenerated: only the previously generated
    ``data/<ns>`` subtree and ``pack.mcmeta`` are removed, never anything
    else under ``out``.
    """
    if not configs:
        raise ValueError("at least one village variant is required")
    for name in configs:
        if not _VARIANT_NAME.match(name):
            raise ValueError(f"invalid variant name for resource paths: {name!r}")
        if not isinstance(configs[name], VillageConfig):
            raise ValueError(f"variant {name!r} is not a VillageConfig")
    out_path = Path(out)
    resolved = out_path.resolve()
    if resolved == _PROJECT_ROOT or resolved.parent == resolved:
        raise ValueError("refusing to build a datapack at the project or filesystem root")
    profile = _load_profile(version)
    pack_format = profile["data_pack_format"]
    data_version = profile["data_version"]

    generated = out_path / "data" / "treehouse_village"
    if generated.exists():
        rmtree(generated)
    mcmeta = out_path / "pack.mcmeta"
    if mcmeta.exists():
        mcmeta.unlink()
    out_path.mkdir(parents=True, exist_ok=True)
    description = (f"Ultimate Treehouse Village ({', '.join(configs)}) "
                   f"for Minecraft {version}")
    mcmeta.write_text(json.dumps({"pack": {
        "description": description,
        "min_format": pack_format,
        "max_format": pack_format,
    }}, indent=2) + "\n", encoding="utf-8", newline="\n")

    serializer = StructureSerializer(data_version=data_version)
    structure_root = out_path / "data" / "treehouse_village" / "structure"
    function_root = out_path / "data" / "treehouse_village" / "function"
    structures: list[Path] = []
    functions: list[Path] = []
    offsets_by_variant: dict[str, list[Vec3]] = {}

    for name, config in configs.items():
        scene = generate_village(config).scene
        segments = segment_scene(scene, max_size=SEGMENT_SIZE)
        if not segments:
            raise ValueError(f"variant {name!r} produced no structure segments")
        target = structure_root / name
        target.mkdir(parents=True, exist_ok=True)
        offsets: list[Vec3] = []
        for index, segment in enumerate(segments):
            bounds = segment.scene.bounds
            if bounds is None:
                raise ValueError(f"variant {name!r} segment {index} is empty")
            template = target / f"{index}.nbt"
            template.write_bytes(serializer.dumps(segment.scene))
            structures.append(template)
            # The serializer normalizes each segment to its own bounds.minimum,
            # so the template origin corresponds to that world cell.
            offsets.append(segment.origin + bounds.minimum)
        offsets_by_variant[name] = offsets

    for shared in ("help", "preview", "status", "cleanup", "showcase/sunset"):
        functions.append(_write_function(
            function_root, f"{shared}.mcfunction",
            _shared_function_lines(shared, configs)))

    for name, config in configs.items():
        offsets = offsets_by_variant[name]
        total = len(offsets)
        variants_lines = {
            "entry": _variant_function_lines(name, "entry", config.width, config.depth,
                                             total, offsets),
            "begin": _variant_function_lines(name, "begin", config.width, config.depth,
                                             total, offsets),
            "check": _variant_function_lines(name, "check", config.width, config.depth,
                                             total, offsets),
            "reject": _variant_function_lines(name, "reject", config.width, config.depth,
                                              total, offsets),
            "force": _variant_function_lines(name, "force", config.width, config.depth,
                                             total, offsets),
            "done": _variant_function_lines(name, "done", config.width, config.depth,
                                            total, offsets),
            "failed": _variant_function_lines(name, "failed", config.width, config.depth,
                                              total, offsets),
        }
        suffix = {"entry": "", "begin": "_begin", "check": "_check",
                  "reject": "_reject", "force": "_force", "done": "_done",
                  "failed": "_failed"}
        for key, lines in variants_lines.items():
            functions.append(_write_function(
                function_root, f"place/{name}{suffix[key]}.mcfunction", lines))
        for k in range(total):
            functions.append(_write_function(
                function_root, f"place/{name}_tick{k}.mcfunction",
                _variant_function_lines(name, "tick", config.width, config.depth,
                                        total, offsets, k)))

    return Datapack(out=out_path, version=version, configs=configs,
                    structures=tuple(structures), functions=tuple(functions))
