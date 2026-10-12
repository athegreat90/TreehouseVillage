"""Isolated exact-server NBT probes, never a village compatibility certificate."""
from __future__ import annotations

from dataclasses import dataclass
import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Sequence
import uuid

from rapidnbt import CompoundTag, IntTag, ListTag, NbtCompressionType, NbtFileFormat, nbtio

from .compatibility import CompatibilityError, DEFAULT_TARGETS
from .server_archive import MAX_ARCHIVE_BYTES, inspect_archive


@dataclass(frozen=True)
class PreparedProbe:
    version: str
    directory: Path
    archive: Path
    token: str


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError(f"path resolves outside the project: {relative}")
    return path


def _fixture(data_version: int) -> CompoundTag:
    def ints(values):
        return ListTag([IntTag(value) for value in values])

    # 26.3 reads lowercase structure-palette keys; earlier targets retain the
    # legacy keys. This is versioned by the verified server DataVersion.
    block_name = "id" if data_version >= 5023 else "Name"
    properties_name = "properties" if data_version >= 5023 else "Properties"
    return CompoundTag({
        "DataVersion": IntTag(data_version),
        "size": ints([1, 2, 1]),
        "palette": ListTag([
            CompoundTag({block_name: "minecraft:jungle_log",
                         properties_name: CompoundTag({"axis": "y"})}),
            CompoundTag({block_name: "minecraft:lantern",
                         properties_name: CompoundTag({"hanging": "false",
                                                    "waterlogged": "false"})}),
        ]),
        "blocks": ListTag([
            CompoundTag({"state": IntTag(0), "pos": ints([0, 0, 0])}),
            CompoundTag({"state": IntTag(1), "pos": ints([0, 1, 0])}),
        ]),
        "entities": ListTag(),
    })


def prepare_probe(root: Path, version: str, *, accept_eula: bool) -> PreparedProbe:
    """Validate everything before creating a fresh, project-local test world."""
    if accept_eula is not True:
        raise ValueError("explicit --accept-eula is required")
    if version not in DEFAULT_TARGETS:
        raise ValueError("version must be an exact configured target ID")
    root = root.resolve(strict=True)
    profile_path = _inside(root, f"config/versions/{version}.json")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("id") != version:
        raise ValueError("profile id does not match requested version")
    archive = _inside(root, profile["archive_path"])
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("server archive exceeds size limit")
    try:
        evidence = inspect_archive(archive.read_bytes(), profile)
    except CompatibilityError as exc:
        raise ValueError(str(exc)) from exc
    formats = evidence["formats"]
    if any(profile["formats"].get(key) != formats[key]
           for key in ("data_version", "data_pack_format")):
        raise ValueError("profile formats do not match verified archive")
    pack_format = formats["data_pack_format"]
    run_id = uuid.uuid4().hex
    directory = _inside(root, f"build/worlds/nbt-smoke/{version}/{run_id}")
    # Refuse output symlink escapes before any mkdir/write.
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "tmp").mkdir()
    (directory / "home").mkdir()
    (directory / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (directory / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=0\nonline-mode=true\n"
        "enable-rcon=false\nenable-query=false\nlevel-name=world\n"
        "level-type=minecraft:flat\nview-distance=2\nsimulation-distance=2\n"
        "max-players=1\nspawn-protection=0\n",
        encoding="utf-8",
    )
    pack = directory / "world/datapacks/treehouse_village_probe"
    functions = pack / "data/treehouse_village_probe/function"
    structures = pack / "data/treehouse_village_probe/structure"
    functions.mkdir(parents=True)
    structures.mkdir(parents=True)
    (pack / "pack.mcmeta").write_text(json.dumps({"pack": {
        "description": "Isolated NBT loading probe, not a village",
        "min_format": pack_format,
        "max_format": pack_format,
    }}, indent=2) + "\n", encoding="utf-8")
    if not nbtio.dump(_fixture(formats["data_version"]), structures / "probe.nbt",
                      format=NbtFileFormat.BIG_ENDIAN,
                      compression_type=NbtCompressionType.GZIP):
        raise OSError("failed to serialize the NBT probe")
    token = f"TV_NBT_PROBE_PASS_{run_id}"
    (functions / "check.mcfunction").write_text(
        "setblock 0 100 0 minecraft:air\n"
        "setblock 0 101 0 minecraft:air\n"
        "place template treehouse_village_probe:probe 0 100 0\n"
        "execute if block 0 100 0 minecraft:jungle_log[axis=y] "
        "if block 0 101 0 minecraft:lantern[hanging=false,waterlogged=false] "
        f"run say {token}\n",
        encoding="utf-8",
    )
    return PreparedProbe(version, directory, archive, token)


def run_console(command: Sequence[str], directory: Path, token: str,
                *, timeout: float) -> dict:
    """Wait on console events; never retry. Stop the child after a deadline."""
    if not 0 < timeout <= 900:
        raise ValueError("timeout must be greater than 0 and at most 900 seconds")
    events: queue.Queue[str | None] = queue.Queue()
    process = subprocess.Popen(
        command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None and process.stdin is not None

    def receive():
        try:
            for line in process.stdout:
                events.put(line)
        finally:
            events.put(None)

    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    ready = False
    passed = False
    timed_out = False
    with (directory / "server-console.log").open("w", encoding="utf-8") as log:
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    line = events.get(timeout=remaining)
                except queue.Empty:
                    timed_out = True
                    break
                if line is None:
                    try:
                        process.wait(timeout=max(0.01, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        timed_out = True
                    break
                log.write(line)
                log.flush()
                if not ready and "[Server thread/INFO]: Done (" in line:
                    ready = True
                    process.stdin.write("function treehouse_village_probe:check\n")
                    process.stdin.flush()
                elif (ready and not passed and "[Server thread/INFO]: " in line
                      and line.rstrip().split("[Server thread/INFO]: ", 1)[1]
                      in {token, f"[Server] {token}", f"[Not Secure] [Server] {token}",
                          f"System chat: [Not Secure] [Server] {token}"}):
                    passed = True
                    process.stdin.write("stop\n")
                    process.stdin.flush()
        finally:
            if process.poll() is None:
                # Timeout/failure terminates only this owned process, not other servers.
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            reader.join(timeout=1)
            process.stdin.close()
            process.stdout.close()
    result = {"passed": passed and not timed_out and process.returncode == 0,
              "exit_code": process.returncode}
    if timed_out:
        result["timed_out"] = True
    return result


def run_probe(probe: PreparedProbe, *, timeout: float) -> dict:
    """Run one verified official server in its disposable working directory."""
    command = [
        "java", "-Xms256M", "-Xmx1G",
        f"-Djava.io.tmpdir={probe.directory / 'tmp'}",
        f"-Duser.home={probe.directory / 'home'}",
        "-jar", str(probe.archive), "nogui",
    ]
    result = run_console(command, probe.directory, probe.token, timeout=timeout)
    result.update({"version": probe.version, "directory": str(probe.directory),
                   "scope": "two-block NBT loading probe only",
                   "village_support": "unverified"})
    (probe.directory / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8",
    )
    return result
