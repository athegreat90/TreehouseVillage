# Exact-server NBT smoke probes

This tests a real gzip Java structure template containing a jungle log and
an upright lantern. It is not a village, release artifact, traversal test,
fluid test, or certificate of full datapack compatibility.

## Prerequisites

- Run from the dedicated `TreehouseVillage` project root.
- Java 25 on PATH and the verified official server archives referenced by
  `config/versions/*.json`.
- The tested Python environment with `rapidnbt==1.3.5`.
- Explicit human acceptance of <https://aka.ms/MinecraftEULA> before invoking
  `--accept-eula`. The script refuses to launch without this flag.

## Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv\Scripts\python.exe scripts/smoke_servers.py --help
# Only after accepting the EULA:
.venv\Scripts\python.exe scripts/smoke_servers.py 26.1.2 --accept-eula --timeout 180
.venv\Scripts\python.exe scripts/smoke_servers.py 26.2 --accept-eula --timeout 180
.venv\Scripts\python.exe scripts/smoke_servers.py 26.3 --accept-eula --timeout 180
```

Omitting version IDs runs all three sequentially, stopping at the first
failure. Version IDs must be unique and exact. The deadline is per server,
includes shutdown, and must be greater than zero and at most 900 seconds.
No failed or timed-out server is automatically retried.

## Isolation and evidence

Each invocation creates a unique disposable directory under
`build/worlds/nbt-smoke/<version>/<run-id>/`. It never opens an existing player
world. The server binds to loopback with an ephemeral port, uses online
mode, disables query/RCON, and has a one-gigabyte Java heap ceiling. Java
temporary files and user-home caches are redirected into the run directory.
Archived server size/SHA-1, embedded version ID and format values are checked
before any new world is created.

The probe datapack uses the version-specific exact `min_format`/`max_format`
pair and the singular `function`/`structure` paths. Those conventions are
under test, not assumed compatible based on the Python fixtures.

After server readiness, the console invokes the probe function. It clears
two test-world positions, places the real template, and uses `execute if
block` to verify both resulting block states. Only that conditional emits
the unique success token. Success also requires clean server shutdown and
exit code zero. A naked token without the server log prefix is not accepted.

Evidence stays in each run directory:

- `server-console.log`: merged stdout/stderr, retained for diagnosis.
- `result.json`: target version, result, exit code, timeout where applicable,
  and explicit `village_support: unverified`.
- Generated probe NBT and datapack inside the disposable world's datapacks.

On timeout the harness terminates only its owned Java child. Interrupted
worlds remain available for inspection; neither existing worlds nor sibling
projects are deleted. A process-start/preparation failure is reported on
stderr and may precede creation of `result.json`.

## Observed results

The first real three-version job exited **1** after 3 minutes 17 seconds.

| Version | Two-block probe | Java exit | Evidence run ID |
| --- | --- | --- | --- |
| 26.1.2 | PASS | 0 | `56758ecc497e4fb182858864e64ca28a` |
| 26.2 | PASS | 0 | `9587dbbc811e475ab2a38d92953bd630` |
| 26.3 | FAIL: 180-second deadline exceeded | 1 | `42a7be3c33b74530bd1e2c2a5e6eea91` |

Each run's files are retained under the version/run directory described above.
26.3 reached readiness (`Done (0.350s)!`) and logged the function invocation,
but did not record the conditional success token. Its cause is not proven;
this was not a slow-startup failure. The same log also reports
`No key layers in MapLike[{}]` during flat-world setup, which needs attention
before further probes. No restart, increased timeout, or success override was
performed. A fresh/corrected 26.3 probe requires an explicit human decision.

All three targets remain **unverified for village support**. The passing
probes only cover these two blocks and the metadata/function/template paths
used by the smoke fixture, not every required registry entry or runtime feature.
Independent runtime review remains pending.

## Offline harness tests

```powershell
New-Item -ItemType Directory -Force build/smoke-tests, build/smoke-full | Out-Null
.venv\Scripts\python.exe -m pytest tests/unit/test_server_smoke.py -q --basetemp build/smoke-tests
.venv\Scripts\python.exe -m pytest -q --basetemp build/smoke-full
```

These use synthetic checksum-valid archive metadata and fake console child
processes. They verify EULA refusal, confinement, real fixture serialization,
console signal/shutdown, deadlines and CLI help. Fake-console results are
never recorded as Minecraft passes. Keep synthetic project root names short
on Windows; no OS long-path or security setting changes are required.
