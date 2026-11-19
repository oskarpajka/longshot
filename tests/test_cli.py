import json

from longshot.cli import main


def test_check_registry_stage(tmp_path):
    reg = tmp_path / "r.csv"
    from longshot import registry

    registry.save(registry.empty(), reg)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"stage: check-registry\nrun_name: t\nregistry: {reg}\n")
    rc = main(["check-registry", "--config", str(cfg), "--results-root", str(tmp_path / "runs"),
               "--allow-dirty"])
    assert rc == 0
    manifests = list((tmp_path / "runs").glob("*/manifest.json"))
    assert len(manifests) == 1
    data = json.loads(manifests[0].read_text())
    assert data["counts"]["rows"] == 0
