"""D018 study: compare scattered-light mask settings on the development sample (inverted flux).

Usage: uv run python scripts/study_bkg_mask.py <dev_search_run_id> [workers]
Writes results/runs/<run_id>_study_bkg-mask/ with a manifest, per-star results and a summary.
"""

from __future__ import annotations

import itertools
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from longshot.manifest import RunManifest
from longshot.pipeline import SearchSettings, search_lightcurve

Z_VALUES = [None, 3.0, 5.0, 10.0]
PAD_VALUES = [0.0, 0.25, 0.5]


def variants():
    out = [(None, 0.0)]
    out += [(z, p) for z, p in itertools.product(Z_VALUES[1:], PAD_VALUES)]
    return out


def one_star(args):
    tic, sectors, settings = args
    from longshot.data import qlp

    base = SearchSettings.from_config(settings)
    rows = []
    for sec in sectors:
        path = qlp.fetch_lightcurve(tic, sec)
        if path is None:
            continue
        lc = qlp.read_lightcurve(path)
        for z, pad in variants():
            s = replace(base, bkg_z_max=z, bkg_pad_d=pad)
            ev, info = search_lightcurve(lc, s, invert=True)
            rows.append({"tic": tic, "sector": sec, "z": -1 if z is None else z, "pad": pad,
                         "max_snr": max((e["snr"] for e in ev), default=0.0),
                         "n_raw": info["n_raw"], "n_good": info["n_good"]})
    return rows


def main() -> int:
    dev_run = Path("results/runs") / sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    settings = yaml.safe_load(Path("configs/search_common.yaml").read_text())
    cfg = {"stage": "study", "run_name": "bkg-mask", "dev_run": dev_run.name,
           "variants": [list(v) for v in variants()], "metric_snr": 10.0}
    man = RunManifest("study", cfg)
    man.add_data_version("dev_run", dev_run.name)
    stars = pd.read_csv(dev_run / "stars.csv.gz")
    jobs = [(int(r.tic), [int(x) for x in str(r.sectors).split()], settings)
            for r in stars.itertuples()]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(one_star, jobs, chunksize=2)):
            rows.extend(r)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(jobs)} stars", flush=True)
    df = pd.DataFrame(rows)
    out = man.run_dir / "per_sector.csv.gz"
    df.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})
    man.add_output(out)
    per_star = df.groupby(["z", "pad", "tic"]).agg(max_snr=("max_snr", "max"),
                                                 n_raw=("n_raw", "sum"),
                                                 n_good=("n_good", "sum")).reset_index()
    summ = per_star.groupby(["z", "pad"]).agg(
        stars=("tic", "size"),
        frac_snr_ge_7_1=("max_snr", lambda x: float(np.mean(x >= 7.1))),
        frac_snr_ge_10=("max_snr", lambda x: float(np.mean(x >= 10))),
        frac_snr_ge_15=("max_snr", lambda x: float(np.mean(x >= 15))),
        max_snr=("max_snr", "max"),
        n_raw=("n_raw", "sum"), n_good=("n_good", "sum")).reset_index()
    summ["data_kept"] = summ["n_good"] / summ["n_raw"]
    best = summ["frac_snr_ge_10"].min()
    ok = summ[summ["frac_snr_ge_10"] <= best + 0.01]
    chosen = ok.sort_values("data_kept", ascending=False).iloc[0]
    summ["chosen"] = (summ["z"] == chosen["z"]) & (summ["pad"] == chosen["pad"])
    out = man.run_dir / "summary.csv"
    summ.to_csv(out, index=False)
    man.add_output(out)
    man.set_count("stars", len(jobs))
    man.set_count("chosen_z", float(chosen["z"]))
    man.set_count("chosen_pad_d", float(chosen["pad"]))
    print(summ.round(4).to_string())
    print("manifest:", man.finish("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
