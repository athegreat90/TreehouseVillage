# Ultimate Treehouse Village

Offline Python tooling that will generate two procedurally composed, vanilla Java treehouse villages (Mega and Compact) as real NBT structures plus a datapack. **Status: M0 compatibility tooling. Exact server format evidence is verified, but no village structures, production placement datapack or release exist yet, and no Minecraft version is certified as supported.**

## Quick path

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m pytest -q --basetemp build/pytest
.venv\Scripts\python.exe scripts\discover_versions.py        # metadata only
.venv\Scripts\python.exe scripts\inspect_servers.py           # downloads and verifies servers; does not launch them
```

Targets are the exact Java versions `26.1.2`, `26.2` and `26.3`. Official metadata existing is not support: see [docs/compatibility/README.md](docs/compatibility/README.md).

## Layout

| Path | Purpose |
|------|---------|
| `src/treehouse_village/` | Compatibility discovery and verified archive inspection |
| `scripts/discover_versions.py` | Compatibility discovery CLI |
| `config/versions/` | Exact-version profiles with embedded server format evidence; runtime support unverified |
| `build/compatibility/` | Per-version evidence and last-run report |
| `tests/unit/` | pytest suite |
| `odd/` | Parent-owned task records (do not edit from tooling) |

## Current checks and blockers

The latest completed offline suite passed **66 tests**, including six NBT
toolchain probes and thirteen server-harness cases. Fake-console tests are not
Minecraft execution evidence. See [exact-server smoke probes](docs/compatibility/server-smoke.md)
for isolated real-server verification. Archive inspection verified:
26.1.2 DataVersion 4790 / data format 101.1; 26.2 DataVersion 4903 / data
format 107.1; 26.3 DataVersion 5023 / data format 121.0. These are not runtime
support claims.

The selected stable NBT dependency is `rapidnbt==1.3.5`, which provides a
Windows Python 3.14 wheel without runtime dependencies. See
[the NBT toolchain](docs/compatibility/nbt-toolchain.md) for the exact
hash-pinned installation and verification boundaries. The existing Python
3.14 interpreter is preserved; the failed Python 3.12 installation is not
retried. The narrow two-block NBT/game-load gate has passed for all three targets;
full village compatibility remains **NOT TESTED**.

## Not done yet

Geometry, NBT serialization, validation, placement, runtime QA and packaging (M1+).
Isolated vanilla servers have now run: the two-block NBT probes passed on
26.1.2, 26.2, and 26.3. See [the probe results](docs/compatibility/server-smoke.md#observed-results).
These narrow probes do not certify village compatibility. The first failed
26.3 run is retained for diagnosis, while the corrected run passed. Push and
publishing remain unauthorized. Full runtime and visual validation are release
gates that static tests do not replace.
