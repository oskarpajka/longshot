"""D019 safety check: does the centroid-motion veto remove real transits?

Confirmed transiting planets (NASA Exoplanet Archive pscomppars) around stars in our target
list, excluding the Phase 1 validation set. At most 3 predicted transits per planet with
expected box SNR >= 7. Reports the fraction with cen_unexpl_z > 5 (the D019 rule).

Usage: uv run python scripts/check_centroid_veto.py [workers]
"""

from __future__ import annotations

import io
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from longshot.manifest import RunManifest
from longshot.stages import resolve_run

Z_VETO = 5.0
SNR_MIN = 7.0
MAX_TRANSITS = 3


def fetch_planets() -> pd.DataFrame:
    q = ("select pl_name,tic_id,pl_orbper,pl_tranmid,pl_trandur,pl_trandep,st_teff from pscomppars"
         " where tran_flag=1 and tic_id is not null and st_teff < 4000")
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode(
        {"query": q, "format": "csv"})
    with urllib.request.urlopen(url, timeout=180) as r:
        df = pd.read_csv(io.BytesIO(r.read()))
    df["tic"] = df["tic_id"].str.replace("TIC", "").str.strip().astype("int64")
    return df


def one_planet(args):
    row, sectors, settings = args
    from longshot.data import qlp
    from longshot.lc.prep import prepare, robust_std
    from longshot.pipeline import SearchSettings, _centroids_at
    from longshot.search.centroid import centroid_stats

    s = SearchSettings.from_config(settings)
    dur_d = row["pl_trandur"] / 24.0
    w = s.window_for(row["pl_trandur"])
    out = []
    for sec in sectors:
        if len(out) >= MAX_TRANSITS:
            break
        path = qlp.fetch_lightcurve(int(row["tic"]), int(sec))
        if path is None:
            continue
        lc = qlp.read_lightcurve(path)
        prep = prepare(lc, [w], s.quality_bitmask, s.gap_d, s.edge_trim_d, s.flare_clip_sigma,
                       bkg_z_max=s.bkg_z_max, bkg_pad_d=s.bkg_pad_d)
        if len(prep.time) < 50:
            continue
        cen = _centroids_at(lc, prep.time)
        if cen is None:
            continue
        resid = prep.detrended[w] - 1.0
        sig = robust_std(resid)
        t = prep.time
        n0 = np.ceil((t[0] - row["pl_tranmid"]) / row["pl_orbper"])
        n1 = np.floor((t[-1] - row["pl_tranmid"]) / row["pl_orbper"])
        for n in np.arange(n0, n1 + 1):
            if len(out) >= MAX_TRANSITS:
                break
            tc = row["pl_tranmid"] + n * row["pl_orbper"]
            inn = (np.abs(t - tc) < dur_d / 2) & np.isfinite(resid)
            n_in = int(inn.sum())
            if n_in < 3 or n_in < 0.5 * dur_d / (lc.cadence_s / 86400):
                continue
            snr = -np.mean(resid[inn]) / (sig / np.sqrt(n_in))
            if snr < SNR_MIN:
                continue
            st = centroid_stats(t, cen[0], cen[1], resid, tc, dur_d, w, s.gap_d)
            out.append({"pl_name": row["pl_name"], "tic": int(row["tic"]), "sector": int(sec),
                        "tc": float(tc), "dur_h": float(row["pl_trandur"]), "snr": float(snr),
                        **st})
    return out


def main() -> int:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    settings = yaml.safe_load(Path("configs/search_common.yaml").read_text())
    cfg = {"stage": "study", "run_name": "centroid-veto", "z_veto": Z_VETO, "snr_min": SNR_MIN,
           "max_transits": MAX_TRANSITS, "search_settings": settings}
    man = RunManifest("study", cfg)
    tdir = resolve_run("20261119T102122Z_targets_mdwarf-tic82", "targets")
    adir = resolve_run("20261119T102416Z_availability_mdwarf-qlp", "availability")
    man.add_data_version("targets_run", tdir.name)
    man.add_data_version("availability_run", adir.name)
    targets = set(pd.read_csv(tdir / "targets.csv.gz", usecols=["ID"])["ID"].astype("int64"))
    av = pd.read_csv(adir / "availability.csv.gz")
    val = {int(t["tic"]) for t in yaml.safe_load(
        Path("configs/validation_targets.yaml").read_text())["targets"]}
    pl = fetch_planets()
    man.add_data_version("nea_pscomppars", "queried live, see planets.csv")
    pl = pl[pl["tic"].isin(targets) & ~pl["tic"].isin(val)]
    pl = pl.dropna(subset=["pl_orbper", "pl_tranmid", "pl_trandur"])
    pl = pl[(pl["pl_trandur"] > 0.4) & (pl["pl_trandur"] <= 12.0)]
    out = man.run_dir / "planets.csv"
    pl.to_csv(out, index=False)
    man.add_output(out)
    secs = av.groupby("tic")["sector"].apply(sorted).to_dict()
    jobs = [(r, secs.get(int(r["tic"]), []), settings) for r in pl.to_dict("records")]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(one_planet, jobs):
            rows.extend(r)
    df = pd.DataFrame(rows)
    out = man.run_dir / "transits.csv"
    df.to_csv(out, index=False)
    man.add_output(out)
    tested = df[np.isfinite(df["cen_unexpl_z"])]
    vetoed = tested[tested["cen_unexpl_z"] > Z_VETO]
    frac = len(vetoed) / max(1, len(tested))
    man.set_count("planets", int(pl.shape[0]))
    man.set_count("transits_tested", len(tested))
    man.set_count("transits_vetoed", len(vetoed))
    man.set_count("fraction_vetoed", round(frac, 4))
    man.set_count("passes_2pct", int(frac <= 0.02))
    print(f"planets {len(pl)}, transits tested {len(tested)}, vetoed {len(vetoed)} ({frac:.3f})")
    print(vetoed[["pl_name", "sector", "snr", "dur_h", "cen_shift", "cen_unexpl_z"]].to_string())
    print(tested["cen_unexpl_z"].describe().round(2).to_string())
    print("manifest:", man.finish("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
