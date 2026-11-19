"""Production-search plumbing: light curve deletion, resumable checkpoints, star selection."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest
from test_prep_pipeline import SETTINGS, fake_lc

from longshot import pipeline, stages
from longshot.cli import main
from longshot.pipeline import SearchSettings

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("keep", [True, False])
def test_search_star_keep_files(tmp_path, monkeypatch, keep):
    f = tmp_path / "lc.fits"
    f.write_bytes(b"x")
    monkeypatch.setattr(pipeline.qlp, "fetch_lightcurve", lambda tic, sec, cache: f)
    monkeypatch.setattr(pipeline.qlp, "read_lightcurve", lambda p: fake_lc())
    ev, info = pipeline.search_star(1, [40], SearchSettings.from_config(SETTINGS),
                                    keep_files=keep)
    assert ev and len(info) == 1
    assert f.exists() == keep


class FakeMan:
    def __init__(self):
        self.data = {"data_versions": {}, "counts": {}}

    def add_data_version(self, k, v):
        self.data["data_versions"][k] = v

    def set_count(self, k, v):
        self.data["counts"][k] = v


def _run_search(tmp_path, monkeypatch, commit, calls):
    def fake_search_star(tic, sectors, s, invert=False, keep_files=True):
        calls.append(tic)
        return ([{"tic": tic, "sector": sectors[0], "t0": float(tic), "snr": 8.0}],
                [{"tic": tic, "sector": sectors[0], "coverage": [[0.0, 1.0]]}])

    monkeypatch.setattr(pipeline, "search_star", fake_search_star)
    monkeypatch.setattr(stages, "select_stars",
                        lambda cfg, man: {t: [10] for t in (5, 1, 4, 2, 3)})
    clean = {"commit": commit, "dirty": False, "branch": "test"}
    monkeypatch.setattr("longshot.manifest.git_state", lambda repo=None: clean)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "stage: search\nrun_name: prod-test\nmode: normal\n"
        f"search_settings: {REPO / 'configs/search_common.yaml'}\n"
        "availability_run: unused\nstars: {}\nworkers: 1\nchunk_stars: 2\n"
        f"checkpoint: true\ncheckpoint_root: {tmp_path / 'ck'}\n")
    root = tmp_path / "runs"
    rc = main(["search", "--config", str(cfg), "--results-root", str(root)])
    assert rc == 0
    return json.loads(max(root.glob("*/manifest.json")).read_text()), root


def test_checkpointed_search_resumes_identically(tmp_path, monkeypatch):
    calls = []
    m1, _ = _run_search(tmp_path, monkeypatch, "a" * 40, calls)
    assert sorted(calls) == [1, 2, 3, 4, 5] and m1["counts"]["stars_from_checkpoint"] == 0
    assert len(list((tmp_path / "ck").glob("*/part_*.pkl.gz"))) == 3
    # Simulate an interruption after the first chunk: drop the later parts and rerun.
    for p in sorted((tmp_path / "ck").glob("*/part_*.pkl.gz"))[1:]:
        p.unlink()
    import time

    time.sleep(1.1)  # run ids have 1 s resolution
    calls.clear()
    m2, _ = _run_search(tmp_path, monkeypatch, "a" * 40, calls)
    assert sorted(calls) == [3, 4, 5]
    assert m2["counts"]["stars_from_checkpoint"] == 2
    assert m1["outputs"]["events.csv.gz"]["sha256"] == m2["outputs"]["events.csv.gz"]["sha256"]
    assert m1["outputs"]["coverage.jsonl.gz"]["sha256"] == (
        m2["outputs"]["coverage.jsonl.gz"]["sha256"])


def test_checkpoint_refuses_other_commit(tmp_path, monkeypatch):
    _run_search(tmp_path, monkeypatch, "a" * 40, [])
    import time

    time.sleep(1.1)
    with pytest.raises(RuntimeError, match="was made with commit"):
        _run_search(tmp_path, monkeypatch, "b" * 40, [])


def test_production_selection_excludes_calibration_sample(monkeypatch):
    """Uses the committed targets and availability runs (no network)."""
    monkeypatch.chdir(REPO)
    cfg = {"availability_run": "20261119T102416Z_availability_mdwarf-qlp",
           "stars": {"all_targets_run": "20261119T102122Z_targets_mdwarf-tic82",
                     "exclude_sample": {"n": 2000, "seed": 20261119,
                                        "targets_run": "20261119T102122Z_targets_mdwarf-tic82"}}}
    man = FakeMan()
    prod = stages.select_stars(cfg, man)
    calib_cfg = {"availability_run": cfg["availability_run"],
                 "stars": {"sample": cfg["stars"]["exclude_sample"]}}
    calib = stages.select_stars(calib_cfg, FakeMan())
    assert len(calib) == 2000
    assert not set(prod) & set(calib)
    assert man.data["counts"]["stars_excluded_sample"] == 2000
    av = pd.read_csv(REPO / "results/runs/20261119T102416Z_availability_mdwarf-qlp/"
                     "availability.csv.gz", usecols=["tic"])
    tg = pd.read_csv(REPO / "results/runs/20261119T102122Z_targets_mdwarf-tic82/"
                     "targets.csv.gz", usecols=["ID"])
    assert len(prod) == len(set(av["tic"]) & set(tg["ID"])) - 2000
    # The committed calibration search used exactly this draw (plus the validation stars).
    with gzip.open(REPO / "results/runs/20261119T104332Z_search_calib-normal/stars.csv.gz") as fh:
        searched = set(pd.read_csv(fh)["tic"])
    assert set(calib) <= searched
