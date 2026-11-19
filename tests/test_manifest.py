import datetime as dt
import json

from longshot.manifest import RunManifest, make_run_id


def test_run_id_format():
    when = dt.datetime(2026, 11, 19, 10, 15, 0, tzinfo=dt.UTC)
    assert make_run_id("search", "pilot run", when) == "20261119T101500Z_search_pilot-run"


def test_manifest_written_with_required_fields(tmp_path):
    cfg = {"stage": "demo", "run_name": "t"}
    man = RunManifest("demo", cfg, results_root=tmp_path)
    out = man.run_dir / "table.csv"
    out.write_text("a,b\n1,2\n")
    man.add_output(out)
    man.set_count("stars", 3)
    man.add_data_version("qlp", "S1-104")
    path = man.finish()
    data = json.loads(path.read_text())
    for key in ("run_id", "git", "config", "config_hash", "packages", "counts",
                "data_versions", "outputs", "started_utc", "finished_utc", "status"):
        assert key in data
    assert data["counts"]["stars"] == 3
    assert data["outputs"]["table.csv"]["bytes"] == 8
    assert data["status"] == "ok"
    assert "commit" in data["git"]
    assert path.parent.parent == tmp_path  # moved out of _inprogress on finish
    assert not any((tmp_path / "_inprogress").iterdir())
