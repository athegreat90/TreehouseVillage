# Ultimate Treehouse Village

Offline Python tooling that will generate two procedurally composed, vanilla Java treehouse villages (Mega and Compact) as real NBT structures plus a datapack. **Status: T6 composes the Compact village (96x96, 5 giant trees, 8 furnished buildings, 7 suspension bridges) from `config/compact.json`, and T7 composes the Mega village (176x176, 9 giant trees, 16 furnished buildings, 15 suspension bridges, 2 waterfall sanctuaries, 3 viewing platforms) from `config/mega.json`, both with validated 3D routes, and T8 assembles the placement datapack (`src/treehouse_village/datapack.py`: version-pinned `pack.mcmeta`, segmented gzip NBT templates, staged placement functions with a marker-carried session), and T9 completes the environment polish (S8-contained water in `buildings/outdoor.py`, deterministic garden flowers and lamp posts via `environment.py`), and T10 adds evidence-gated release packaging (`scripts/build_release.py` → `dist/` ZIPs with `pack.mcmeta` at the archive root plus `SHA256SUMS.txt`) with CI/release workflows under `.github/workflows/`. In-game runtime and client visual QA gates (S14) remain incomplete, and no public release has been published. Exact server formats and narrow two-block NBT gates do not certify full-village Minecraft support.**

## Quick path

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m pytest -q --basetemp build/pytest
.venv\Scripts\python.exe scripts\discover_versions.py        # metadata only
.venv\Scripts\python.exe scripts\inspect_servers.py           # downloads and verifies servers; does not launch them
.venv\Scripts\python.exe scripts\build_release.py              # evidence-gated version ZIPs + SHA256SUMS.txt -> dist/
```

Targets are the exact Java versions `26.1.2`, `26.2` and `26.3`. Official metadata existing is not support: see [docs/compatibility/README.md](docs/compatibility/README.md).

## Layout

| Path | Purpose |
|------|---------|
| `src/treehouse_village/` | Compatibility, sparse geometry, deterministic tree/home generation, building contracts, village composition, and archive inspection |
| `config/compact.json` | Declarative Compact layout: trees, buildings, bridges, route destinations |
| `config/mega.json` | Declarative Mega layout: 9 trees, 16 buildings, 15 bridges |
| `docs/homes.md` | Residential home designs, generation API, coverage and support-checker limits |
| `scripts/discover_versions.py` | Compatibility discovery CLI |
| `scripts/build_release.py` | Evidence-gated release ZIPs + `SHA256SUMS.txt` |
| `.github/workflows/` | CI (offline suite) and release (artifact) workflows |
| `config/versions/` | Exact-version profiles with embedded server format evidence; runtime support unverified |
| `build/compatibility/` | Per-version evidence and last-run report |
| `tests/unit/` | pytest suite |
| `odd/` | Parent-owned task records (do not edit from tooling) |

## Current checks and blockers

The latest completed offline suite passed **234 tests**, including the Compact and
Mega village integration suites (config loading, counts, footprint, building
contracts, 3D route reachability, ground plane, tree platforms, determinism and
gzip segment reconstruction), the datapack assembly suite (version-pinned
`pack.mcmeta`, gzip NBT segment templates, staged placement functions with
relative offsets and no forbidden world mutations), the environment suite
(geometric water containment per S8, deterministic flowers and lamp posts that
keep every route walkable), the release packaging suite (evidence-gated ZIPs
with `pack.mcmeta` at the archive root and idempotent `SHA256SUMS.txt`), the
single-tree foundation,
building-contract tests, and furnished-home tests. See [building
contracts](docs/building-contracts.md) and [furnished homes](docs/homes.md) for
coverage, required fixture states, and support-checker limitations. Fake-console tests are not
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
full village compatibility remains **NOT TESTED**. No furnished-home game placement
or client visual check has run. The generic direct-below support checker still
reports known horizontal ceiling-span and hanging-lantern warnings; T4b tests verify
their explicit structural anchors rather than claiming that helper is warning-free.

## Not done yet

Everything offline is implemented and merged: both composed villages (T6/T7),
bridges and routes (T5), the building catalogue including furnished homes
(T4a–T4e), the placement datapack (T8), environment polish (T9) and release
packaging with CI (T10). See the [final report](docs/final-report.md) for the
delivery ledger and verification summary.

Still open:

- **Full-village in-game placement and runtime QA** on exact servers.
- **Client visual QA (S14)** — an explicit release gate.
- **Fluid ticks (S8)**: validate water behaviour after game ticks when
  in-game testing is available.
- **Version support claims**: every evidence file reads `support: unverified`,
  `runtime_qa: pending`.
- **Publishing a release**: CI builds the artifacts; creating a public
  GitHub Release stays a human decision.

Isolated vanilla servers have now run: the two-block NBT probes passed on
26.1.2, 26.2, and 26.3. See [the probe results](docs/compatibility/server-smoke.md#observed-results).
These narrow probes do not certify village compatibility. The first failed
26.3 run is retained for diagnosis, while the corrected run passed. The user has authorized per-task feature branches, verified commits, pushes,
issue-linked PRs and merges to `main`, followed by local/remote main synchronization. Full runtime and visual validation are release
gates that static tests do not replace.
