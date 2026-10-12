# NBT toolchain

## Selection

Use stable `rapidnbt==1.3.5` for Java big-endian NBT. The Windows x64
CPython 3.14 wheel is available without runtime dependencies; no alpha
Amulet dependency or replacement Python installation is required.

Primary evidence checked on 2026-10-12:

- <https://pypi.org/pypi/rapidnbt/1.3.5/json>
- <https://github.com/GlacieTeam/RapidNBT>
- <https://api.github.com/repos/GlacieTeam/RapidNBT>

The wheel was uploaded on 2025-12-16. The upstream repository is not
archived; its last reported push is 2025-12-18. This records observable
maintenance evidence, not a guarantee of continued maintenance. Lack of
recent releases alone does not establish that another library is abandoned.

## Windows Python 3.14 installation

Run from the project root. Keep pip cache and temporary directories under
`build`, as required by the project-local artifact policy:

```powershell
New-Item -ItemType Directory -Force build/pip-cache, build/tmp/pip-nbt, build/pytest-nbt | Out-Null
$env:PIP_CACHE_DIR = Join-Path $PWD 'build/pip-cache'
$env:TMP = Join-Path $PWD 'build/tmp/pip-nbt'
$env:TEMP = $env:TMP
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: --no-deps -r config/requirements-nbt-windows-py314.txt
.venv\Scripts\python.exe -m pytest tests/unit/test_nbt_toolchain.py -q --basetemp build/pytest-nbt
```

The requirement pins the exact wheel and its PyPI SHA-256:
`37268f485bd5d660282c8e5490fe5ad4cbef50dadc3559133560285315b508ad`.
This file is specific to Windows x64 CPython 3.14. It is not a portable
lockfile. Other environments must resolve the pinned package version to a
compatible wheel and validate it independently; source compilation is not
an implicit fallback.

## Verification boundaries

Importing the library does not prove structure validity. Public API tests
must check typed Java big-endian serialization and gzip decompression,
including an empty root name, homogeneous integer coordinate lists, and
compound block lists. Binary output is independently checked rather than
only round-tripping through the same library.

A small NBT fixture is exclusively a toolchain test, not a village asset.
Exact-version Minecraft loading remains a separate gate. No supported
Minecraft version, finished village, or distributable ZIP is implied.

## Preserved environment incident

The earlier project-local Python 3.12 installation failed with Windows
access denied during a directory rename. Its cause remains unproven. Do
not automatically retry it, change permissions, or bypass security tools.
The existing Python 3.14 interpreter and historical installation artifacts
are preserved.
