# Compatibility discovery

`scripts/discover_versions.py` records what Mojang's official metadata says about `26.1.2`, `26.2` and `26.3`. It does **not** establish support.

## Quick path

```powershell
.venv\Scripts\python.exe scripts\discover_versions.py            # all three targets
.venv\Scripts\python.exe scripts\discover_versions.py 26.3 --timeout 10
```

Exit code: `0` all targets resolved or explicitly unavailable, `1` a request/verification failed, `2` unsafe argument.

## How it works

1. Fetch `https://piston-meta.mojang.com/mc/game/version_manifest_v2.json` (HTTPS, Mojang hosts only, no redirects, 20 s timeout, 8 MiB cap).
2. Match each target by **exact id**. No prefix, snapshot, RC or "nearest" substitution.
3. Fetch the version metadata URL (4 MiB cap) and verify its SHA1 against the manifest.
4. Record official type, release status, source URLs, server download URL/SHA1/size and required Java.
5. Write stable, atomically replaced JSON. The server jar is never downloaded.

## Outputs

| File | Meaning |
|------|---------|
| `build/compatibility/<id>.json` | Full evidence including sources |
| `build/compatibility/last-run.json` | Outcome per target (git-ignored) |
| `config/versions/<id>.json` | Profile derived from the evidence |

Writes are confined to those two directories inside the project root.

## Field semantics

| Field | Values |
|-------|--------|
| `status` | `metadata_found` or `unavailable` (id absent from manifest) |
| `release_status` | `official_release` only when manifest type is `release`; otherwise `not_official_release` |
| `support` | `unverified` (never upgraded by this tool) or `unsupported_unavailable` |
| `runtime_qa` | `pending` until a verifier runs the exact server |
| `formats.*` | `"unknown"` unless the version metadata states `world_version` / `pack_version`; Mojang's launcher metadata currently does not, so DataVersion, data-pack and resource-pack formats remain unknown |

A failed request (network, size, SHA1 mismatch, malformed metadata) never overwrites existing evidence; it is reported in `last-run.json` and the exit code.

## Observed exact-version evidence

All three IDs were present with type `release` and Java major 25
(`java-runtime-epsilon`). Official server archives were downloaded, verified
against declared size/SHA1, and inspected without executing Java:

| Exact version | Structure DataVersion | Datapack format | Resource-pack format |
|---|---:|---|---|
| 26.1.2 | 4790 | 101.1 | 84.0 |
| 26.2 | 4903 | 107.1 | 88.0 |
| 26.3 | 5023 | 121.0 | 97.1 |

The embedded schema uses `data_major`, `data_minor`, `resource_major`, and
`resource_minor`. Profiles preserve pairs as JSON arrays. Source checksums and
embedded version data remain in each evidence file. **These format values are
verified; Minecraft functional compatibility is NOT TESTED.** No server was
launched and no village NBT or distributable archive exists yet.

## Server archive inspection

```powershell
.venv\Scripts\python.exe scripts\inspect_servers.py --help
.venv\Scripts\python.exe scripts\inspect_servers.py 26.1.2 --timeout 30
```

This separate command downloads official server archives after fresh exact-version
metadata discovery. It verifies their declared size and SHA1, reads embedded
`version.json` directly or from the server bundler, and records authoritative
format evidence. It does **not** execute Java or accept the Minecraft EULA.
Verified cached archives are reused and rechecked against fresh metadata; a
corrupt cache is rejected rather than silently replaced. Archives remain in
ignored `build/server-cache/`; profiles and evidence retain
`support: unverified` and `runtime_qa: pending`.

Exit code: `0` requested archives inspected, `1` download/integrity/schema failure,
`2` rejected arguments. Failed inspection does not replace that version's profile.
There are no automatic retries. Integrity/schema tests include deliberately
corrupt archives, wrong versions, duplicate entries and invalid format values.

## Open gates

- [x] DataVersion and pack formats from size/SHA1-verified official server `version.json`.
- [ ] Tiny real NBT load check on each exact server.
- [ ] Runtime and visual QA before any support claim.
