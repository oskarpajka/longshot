"""D020 safety check: how often does the asteroid veto fire by chance on a random epoch?

300 (star, sector, period, radius, b) combinations from the D015 injection draw (same seed),
with t0 uniform over the sector, depth k^2 and the transit duration. Each is queried with the
D020 rule. If more than 1% are vetoed, the veto is dropped.

Usage: uv run python scripts/check_asteroid_veto.py [n]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from longshot.data import qlp
from longshot.inject.model import a_over_rs, total_duration_d
from longshot.inject.run import draw_injections
from longshot.manifest import RunManifest
from longshot.stages import resolve_run, select_stars
from longshot.vet.asteroids import asteroid_veto


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    icfg = yaml.safe_load(Path("configs/inject_calib.yaml").read_text())
    cfg = {"stage": "study", "run_name": "asteroid-veto", "n": n, "inject_config": icfg,
           "max_fraction": 0.01}
    man = RunManifest("study", cfg)
    stars = select_stars(icfg, man)
    tdir = resolve_run(icfg["stars"]["sample"]["targets_run"], "targets")
    tab = pd.read_csv(tdir / "targets.csv.gz",
                      usecols=["ID", "rad", "mass", "ra", "dec", "Tmag"]).set_index("ID")
    rows = []
    for tic, secs in sorted(stars.items()):
        if tic in tab.index and np.isfinite(tab.loc[tic, "rad"]) and np.isfinite(
                tab.loc[tic, "mass"]):
            rows.extend((tic, s, float(tab.loc[tic, "rad"]), float(tab.loc[tic, "mass"]))
                        for s in secs)
    ic = icfg["injections"]
    rng = np.random.default_rng(int(ic["seed"]))
    injs = draw_injections(rows, int(ic["n"]), rng, tuple(ic["rp_earth"]),
                           tuple(ic["period_d"]), float(ic["b_max"]))[:n]
    trng = np.random.default_rng(20261122)
    out = []
    for i, inj in enumerate(injs):
        path = qlp.fetch_lightcurve(inj.tic, inj.sector)
        if path is None:
            continue
        lc = qlp.read_lightcurve(path)
        t0 = float(trng.uniform(np.nanmin(lc.time), np.nanmax(lc.time)))
        aors = a_over_rs(inj.period_d, inj.mstar, inj.rstar)
        dur = total_duration_d(inj.period_d, aors, inj.k, inj.b)
        depth = inj.k ** 2
        st = tab.loc[inj.tic]
        r = asteroid_veto(t0, dur, depth, float(st["ra"]), float(st["dec"]), float(st["Tmag"]))
        out.append({"tic": inj.tic, "sector": inj.sector, "t0": t0, "dur_d": dur,
                    "depth": depth, **r})
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(injs)}", flush=True)
    df = pd.DataFrame(out)
    p = man.run_dir / "random_epochs.csv"
    df.to_csv(p, index=False)
    man.add_output(p)
    frac = float(df["ast_veto"].mean())
    man.set_count("tested", len(df))
    man.set_count("vetoed", int(df["ast_veto"].sum()))
    man.set_count("fraction_vetoed", round(frac, 4))
    man.set_count("unresolved", int(df["ast_unresolved"].sum()))
    man.set_count("passes_1pct", int(frac <= 0.01))
    print(df[df["ast_veto"]].to_string())
    print(f"tested {len(df)}, vetoed {int(df['ast_veto'].sum())} ({frac:.4f}), "
          f"with bright candidates {int((df['ast_n_bright'] > 0).sum())}")
    print("manifest:", man.finish("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
