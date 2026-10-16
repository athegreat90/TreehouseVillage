# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this is

Offline Python tooling that generates two procedurally composed, vanilla Java
treehouse villages (Mega 176x176 and Compact 96x96) as real gzipped NBT
templates plus a version-pinned placement datapack for the exact Java targets
`26.1.2`, `26.2` and `26.3`. Nothing here launches the game: every claim must
be backed by a check that actually ran.

## Quick path

1. **Install**: `python -m venv .venv && .venv\Scripts\python.exe -m pip install -e ".[test]"`
2. **Test (offline)**: `.venv\Scripts\python.exe -m pytest -q` — no Minecraft, no network; use `PYTHONDONTWRITEBYTECODE=1` and `--basetemp build/<dir>` to keep scratch files project-local.
3. **Release ZIPs**: `.venv\Scripts\python.exe scripts\build_release.py` — evidence-gated; writes `dist/treehouse-village-<version>.zip` + `dist/SHA256SUMS.txt` (both gitignored).
4. **Version metadata**: `scripts/discover_versions.py` (metadata only). Server smoke probes require an explicit `--accept-eula` on `scripts/smoke_servers.py`.

## Layout

| Path | Purpose |
|------|---------|
| `src/treehouse_village/` | geometry, validation, generators, buildings, bridges, village composition, config, datapack, environment, packaging |
| `config/` | `compact.json`, `mega.json`, `versions/<v>.json` profiles |
| `scripts/` | discovery, inspection, smoke and release CLIs |
| `tests/unit/`, `tests/integration/` | offline pytest suite (234 tests) |
| `build/compatibility/` | tracked per-version evidence; everything else under `build/` is disposable |
| `docs/` | compatibility evidence, building contracts, homes, final report |
| `odd/tasks/ultimate-treehouse-village.md` | spec S1–S16, task rows and Log — single source of progress |
| `.github/workflows/` | CI (offline suite) and release (ZIP + checksum artifacts) |

## Rules that break the build or the truth if ignored

- [ ] Everything stays inside this project root; never touch sibling datapack projects (S1).
- [ ] Never claim a version is supported unless its format/functional checks passed; never claim an in-game test passed unless it actually ran (S2, S10).
- [ ] Generators are deterministic: same config + seed → same geometry; no wall-clock or unseeded randomness in geometry paths (S10).
- [ ] Water requires containment/support geometry **before** the source: `validate_water_containment` must stay green (S8).
- [ ] Decor must keep `NODE_CLEARANCE` around route nodes; `validate_routes` must stay green (S9).
- [ ] Placement functions never emit `gamerule`/`weather`/`difficulty`/`forceload`/`tp`/absolute `place template`; only `showcase/sunset` may run `time set` (S9).
- [ ] Native ASSESS needs the real full SHA from `git rev-parse` — fabricated SHAs fail.
- [ ] Delivery per task: feature branch → work-unit Conventional Commit → committed-range ASSESS → push → PR with non-closing `Refs #1` and exactly the `type:feature` label → merge after checks → sync local/remote `main` → record identities in the tracker.

## Before you claim "done"

- [ ] Focused tests + full suite green after the last code change; `git diff --check` clean.
- [ ] README counts and tracker row/Log updated in the same work-unit commit.
- [ ] Disclosures present: `support: unverified`, `runtime_qa: pending`, no in-game QA claimed.
