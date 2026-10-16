# MEMORY.md

Durable knowledge for this repository. **Live status lives in
`odd/tasks/ultimate-treehouse-village.md`** (spec + task rows + Log); this file
keeps only what stays true across tasks.

## What this project is

Offline Python tooling that generates two procedurally composed, vanilla Java
treehouse villages — **Mega (176x176)** and **Compact (96x96)** — as real
gzipped NBT templates plus a version-pinned placement datapack for the exact
Java targets `26.1.2`, `26.2` and `26.3`.

## Hard constraints

- **Confined root**: sources, tests, docs, artifacts and caches all stay in
  this directory; sibling datapack projects are never touched (S1).
- **No unbacked claims**: never state that a version is supported or that an
  in-game test passed unless the relevant check actually ran (S2, S10).
  Evidence currently reads `support: unverified`, `runtime_qa: pending`.
- **Static ≠ runtime**: pytest proves geometry, contracts and routes; it is
  not Minecraft execution.

## Map

| Path | Know this |
|------|-----------|
| `src/treehouse_village/` | geometry, validation (routes, water containment), generators, buildings, bridges, village composition, `datapack.py`, `environment.py`, `packaging.py` |
| `config/` | `compact.json`, `mega.json`, `versions/<v>.json` profiles (pack/data/resource formats) |
| `scripts/` | `discover_versions.py`, `inspect_servers.py`, `smoke_servers.py` (needs `--accept-eula`), `build_release.py` |
| `tests/unit/`, `tests/integration/` | 234 offline tests; runner: `.venv\Scripts\python.exe -m pytest -q` |
| `build/compatibility/` | tracked per-version evidence JSON; everything else under `build/` is disposable |
| `docs/` | compatibility evidence, building contracts, homes, final report |
| `odd/tasks/ultimate-treehouse-village.md` | spec S1–S16, task rows, Log — source of truth for status and identities |

## Decisions that are easy to re-litigate (don't)

| Decision | Why |
|----------|-----|
| Platform radius **10** in both variants | tree branches reach 9 blocks on every axis; radius 4 always collided (60-seed exhaustion proved it structural, not a seed problem) |
| Fixed hall origins `(41,0,41)` / `(41,0,81)` | tests pin the hall trunk cell `(47,0,47)` / `(47,0,87)` |
| `SEGMENT_SIZE = 48x32x48` | datapack staged offsets equal `seg.origin + bounds.minimum`; keeps the bucket count stable |
| Palette keys: `data_version ≥ 5023` → `id`/`properties`, else `Name`/`Properties` | matches the exact servers' serializers |
| `pack.mcmeta` uses `min_format`/`max_format` arrays copied from the version profile | verified by the smoke probes; `pack_format` alone is not the evidence |
| Water containment is geometric: support below + all four sides closed (`validate_water_containment`) | offline proxy for S8; fluid ticks remain a runtime gate |
| Decor (`environment.py`) = fixed lattices with `NODE_CLEARANCE` | deterministic (S10) and never severs routes (S9) |
| `rapidnbt==1.3.5` pinned and hash-verified | the Windows Python 3.14 wheel that works; the 3.12 install attempt is abandoned on purpose |
| Native ASSESS needs the **real full SHA** from `git rev-parse` | fabricated SHAs fail; range via `{baseRef, committedOnly: true}` |

## Verification ledger (what is actually proven)

- Offline suite: **234 passed** (no Minecraft, no network inside tests); it grew
  from 66 at T0 and every step is recorded in the tracker Log.
- Exact-server two-block NBT probes: **PASS** on 26.1.2, 26.2 and 26.3; the
  first 26.3 run failed and is kept for diagnosis.
- Archive evidence: server sha1 + size verified; formats 26.1.2 `[101,1]` /
  4790, 26.2 `[107,1]` / 4903, 26.3 `[121,0]` / 5023.
- Every committed-range ASSESS: medium risk, `reviewDue=false`.
- **Not proven**: full-village in-game placement, client visual QA, fluid
  ticks, version support (`support: unverified`, `runtime_qa: pending`).

## Release rule

`scripts/build_release.py` refuses to label an artifact without evidence
(profile match + verified server sha1); every ZIP carries `pack.mcmeta` at the
archive root (S11); `dist/SHA256SUMS.txt` holds `<sha256>  <filename>` lines
and replaces them on rebuild (S12). `dist/` is gitignored — artifacts are
rebuilt by CI (`.github/workflows/release.yml`), never committed. Publishing a
GitHub Release is a human decision.

## Where to look first

1. Status and identities → tracker `## Tasks` rows + `## Log`.
2. How to work in this repo → `CLAUDE.md`.
3. What shipped and what is *not* proven → `docs/final-report.md`, `README.md`.
