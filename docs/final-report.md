# Ultimate Treehouse Village — Final Report (T0–T10)

**Both villages, the placement datapack and evidence-gated release packaging are
built and green on a static suite of 234 tests, and merged to `main` (T1–T10;
T10 via PR #14). What is *not* proven — in-game placement, client visual QA,
fluid ticks and therefore version support — is stated explicitly below and must
not be glossed over (S2, S10).**

## Quick path

1. **Verify**: `.venv\Scripts\python.exe -m pytest -q` → 234 passed (static, offline).
2. **Build artifacts**: `.venv\Scripts\python.exe scripts\build_release.py`
   → `dist/treehouse-village-{26.1.2,26.2,26.3}.zip` + `dist/SHA256SUMS.txt`.
3. **Check one ZIP**: `pack.mcmeta` must be the archive root entry (no wrapping
   folder, S11) and its hash must match the `SHA256SUMS.txt` line (S12).

## What shipped

| Deliverable | Where | Proof |
|-------------|-------|-------|
| Exact-version compatibility gate | `compatibility/`, `config/versions/`, `build/compatibility/` | evidence JSON per target; sha1+size verified ×3 |
| Geometry / gzip NBT serialization | `geometry/`, `serialization/` | round-trip + legacy/modern palette tests |
| Structural & 3D-movement validation | `validation/` | broken fixtures make tests fail |
| Trees, 15+ building designs, bridges, routes | `generator/`, `buildings/`, `bridges/`, `routes.py` | contracts, counts, reachability, determinism |
| Mega + Compact villages | `village.py` + `config/{mega,compact}.json` | counts, footprint, routes, gzip segment reconstruction |
| Placement datapack (S9) | `datapack.py` | version-pinned `pack.mcmeta`, staged relative `place template`, forbidden-token guards, marker session |
| Environment (S8/S9) | `environment.py`, `validate_water_containment` | geometric water containment; decor lattices keep every route walkable |
| Release packaging (S11/S12) | `packaging.py`, `scripts/build_release.py` | evidence gate, root `pack.mcmeta`, idempotent `SHA256SUMS.txt` |
| CI + release workflows | `.github/workflows/` | offline suite on ubuntu+windows (py3.14); tag/dispatch builds ZIPs as artifacts |
| Docs | `README.md`, `CLAUDE.md`, `MEMORY.md`, `docs/` | this report + compatibility evidence |

## Delivery ledger (T1–T10 merged to `main`)

| Task | Commit | PR | Merge |
|------|--------|----|-------|
| T0 bootstrap + runtime gate | `9754e79` | — | — |
| T1 geometry/serialization | `9d26d7a` | — | — |
| T2 validation foundation | `70196c9` | — | — |
| T3 tree platform foundation | `ed7f228` | #2 | `4dd4166` |
| T4a building contracts | `f4377e1` | #3 | `3a7646a` |
| T4b furnished homes | `5bbc772` | #4 | `a4d3347` |
| T4c civic interiors + entities | `91be481`, `d080388` | #5, #6 | `08c9e11`, `11ccc6a` |
| T4d outdoor catalogue | `8eeb1b2` | #7 | `d188961` |
| T4e village hall | `8babd64` | #8 | `cab136d` |
| T5 bridges + routes | `d7b181d` | #9 | `0fa019c` |
| T6 Compact village | `d73c917` | #10 | `ff9854a` |
| T7 Mega village | `22c3df2` | #11 | `41f9bd9` |
| T8 placement datapack | `a5417a7` | #12 | `8d91e3a` |
| T9 environment | `51488da` | #13 | `6fbb0c8` |
| T10 docs/CI/packaging | `bf50650`, `432bb9e`, `817bed1` | #14 | `97c7d88` |

The tracker Log (`odd/tasks/ultimate-treehouse-village.md`) carries the full
identities for every slice, including the T10 record written after its merge.

## Verification summary

| Gate | Result |
|------|--------|
| Static suite | **234 passed** — unit + integration, no Minecraft, no network in tests |
| Suite growth | 66 (T0) → 186 (T6) → 210 (T8) → 226 (T9) → **234 (T10)**; every step in the Log |
| Native ASSESS per work-unit | T1–T9: medium risk, `reviewDue=false`; T10: high risk, `reviewDue=true` → native review approved + acknowledged |
| Exact-server two-block probes | PASS on 26.1.2 / 26.2 / 26.3 (`docs/compatibility/server-smoke.md`) |
| Release build e2e | 3/3 versions: evidence gate → ZIP with root `pack.mcmeta` (106 entries) → `SHA256SUMS.txt` |

## Version evidence (what justifies a labeled artifact)

| Target | data_pack_format | data_version | server sha1 verified | support | runtime_qa |
|--------|------------------|--------------|----------------------|---------|------------|
| 26.1.2 | `[101, 1]` | 4790 | yes | **unverified** | **pending** |
| 26.2 | `[107, 1]` | 4903 | yes | **unverified** | **pending** |
| 26.3 | `[121, 0]` | 5023 | yes | **unverified** | **pending** |

Official metadata plus the narrow two-block gate justify *producing* a
version-labeled artifact (S11); they do **not** justify a support claim (S2).

## Not verified — do not claim otherwise

- **Full-village in-game placement** on any exact server.
- **Client visual QA** (S14 is an explicit release gate).
- **Vanilla fluid ticks** (S8's second sentence: validate after game ticks when
  in-game testing is available).
- **Version support**: every evidence file reads `support: unverified`,
  `runtime_qa: pending`.
- Known static-checker warnings (horizontal ceiling spans, hanging lanterns)
  are documented in `docs/homes.md`, not silently silenced.

## Release artifacts

| Artifact | Rule |
|----------|------|
| `dist/treehouse-village-<version>.zip` | evidence-gated; `pack.mcmeta` at archive root, no wrapping folder (S11) |
| `dist/SHA256SUMS.txt` | `<sha256>  <filename>` per line; rebuilt, never duplicated (S12) |
| `dist/` | gitignored — on `v*` tags CI rebuilds artifacts and attaches them to a draft GitHub Release; manual dispatch is a build-only dry run; publishing stays a human decision |

## Next step

1. **Client visual QA on an exact server (S14) + fluid-tick observation (S8)** — the only remaining gates before any `support` claim.
2. If the gates pass: refresh the evidence JSONs (`support`/`runtime_qa`), then review the draft GitHub Release the `v*` tag run produced and publish it (human decision).
3. T10 identities live in the tracker Log.
