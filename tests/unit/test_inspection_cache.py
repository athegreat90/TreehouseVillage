"""A verified cached server is inspected without another network download."""
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/inspect_servers.py"
spec = importlib.util.spec_from_file_location("inspect_servers", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_cached_archive_avoids_download(tmp_path, monkeypatch, capsys):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("version.json", json.dumps({"id": "26.1.2", "world_version": 4790,
            "pack_version": {"data_major": 101, "data_minor": 1,
                             "resource_major": 84, "resource_minor": 0}}))
    raw = stream.getvalue()
    sha = hashlib.sha1(raw).hexdigest()
    cache = tmp_path / "build/server-cache"
    cache.mkdir(parents=True)
    target = cache / f"26.1.2-{sha}.jar"
    target.write_bytes(raw)
    record = {"id": "26.1.2", "status": "metadata_found", "official_type": "release",
        "server": {"size": len(raw), "sha1": sha, "url": "https://piston-data.mojang.com/test"},
        "support": "unverified", "runtime_qa": "pending"}
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "discover", lambda *a, **k: {"26.1.2": record})
    def forbidden(*args, **kwargs):
        raise AssertionError("cached archive must not be downloaded")
    monkeypatch.setattr(cli, "fetch_bytes", forbidden)
    assert cli.main(["26.1.2"]) == 0
    out = capsys.readouterr()
    assert "Using cached official server 26.1.2" in out.out
    assert out.err == ""
    profile = json.loads((tmp_path / "config/versions/26.1.2.json").read_text())
    assert profile["formats"]["data_pack_format"] == [101, 1]
    assert profile["support"] == "unverified"
    assert target.read_bytes() == raw
