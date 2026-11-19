"""Common-mode bad-times table (D022).

Scattered light and other spacecraft systematics hit many stars on a camera or CCD at the
same time. A fixed reference set of stars gives, per (sector, camera) and (sector, camera,
CCD), the 1 h bins where many stars deviate together. The search drops those cadences.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from longshot.lc.prep import robust_std

BIN_D = 1.0 / 24.0
Z_DEV = 3.0
MIN_DEV_STARS = 3
MIN_DEV_FRAC = 0.25
WIDEN_BINS = 1


def bin_index(time: np.ndarray) -> np.ndarray:
    return np.floor(np.asarray(time) / BIN_D).astype(np.int64)


def star_bins(time: np.ndarray, resid: np.ndarray, cadence_s: float):
    """(bins with enough data, deviant flag) for one star-sector."""
    ok = np.isfinite(time) & np.isfinite(resid)
    if ok.sum() < 50:
        return np.array([], np.int64), np.array([], bool)
    b = bin_index(time[ok])
    ub, inv = np.unique(b, return_inverse=True)
    n = np.bincount(inv)
    mean = np.bincount(inv, weights=resid[ok]) / n
    keep = n >= 0.5 * BIN_D * 86400.0 / cadence_s
    ub, mean = ub[keep], mean[keep]
    if len(mean) < 10:
        return np.array([], np.int64), np.array([], bool)
    s = robust_std(mean)
    if not np.isfinite(s) or s <= 0:
        return np.array([], np.int64), np.array([], bool)
    return ub, np.abs(mean / s) > Z_DEV


def bad_bins(rows: pd.DataFrame) -> pd.DataFrame:
    """rows: sector, camera, ccd, tic, bin, dev. Returns sector, camera, ccd (-1 = whole
    camera), bin for bad bins, widened by WIDEN_BINS."""
    out = []
    for keys, level_ccd in ((["sector", "camera"], False), (["sector", "camera", "ccd"], True)):
        g = rows.groupby([*keys, "bin"]).agg(n=("tic", "nunique"), n_dev=("dev", "sum"))
        g = g.reset_index()
        bad = g[(g["n_dev"] >= MIN_DEV_STARS) & (g["n_dev"] >= MIN_DEV_FRAC * g["n"])]
        if not level_ccd:
            bad = bad.assign(ccd=-1)
        out.append(bad[["sector", "camera", "ccd", "bin"]])
    bad = pd.concat(out, ignore_index=True)
    widened = [bad.assign(bin=bad["bin"] + k) for k in range(-WIDEN_BINS, WIDEN_BINS + 1)]
    return (pd.concat(widened, ignore_index=True).drop_duplicates()
            .sort_values(["sector", "camera", "ccd", "bin"]).reset_index(drop=True))


@lru_cache(maxsize=4)
def load_table(path: str) -> dict[tuple[int, int, int], np.ndarray]:
    df = pd.read_csv(path)
    return {(int(s), int(c), int(d)): np.sort(g["bin"].to_numpy(np.int64))
            for (s, c, d), g in df.groupby(["sector", "camera", "ccd"])}


def keep_mask(time: np.ndarray, sector: int, camera: int, ccd: int, path: str | Path | None):
    """True where the cadence is not in a bad bin for this camera or CCD."""
    keep = np.ones(len(time), dtype=bool)
    if path is None:
        return keep
    table = load_table(str(path))
    b = bin_index(np.nan_to_num(time, nan=-1e9))
    for key in ((sector, camera, -1), (sector, camera, ccd)):
        bad = table.get(key)
        if bad is not None and len(bad):
            keep &= ~np.isin(b, bad)
    return keep
