"""Light curve preparation: masking, normalization and detrending.

We search QLP SAP flux with our own detrending (D011) so that injection-recovery tests pass
through exactly the same processing as the real data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from wotan import flatten

from longshot.data.qlp import LightCurve


@dataclass
class Prepared:
    time: np.ndarray
    flux: np.ndarray  # normalized raw flux (median 1 per orbit), after masking
    detrended: dict[float, np.ndarray]  # window_length_d -> flux / trend
    sector: int
    cadence_s: float
    n_masked: int


def robust_std(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def good_mask(lc: LightCurve, quality_bitmask: int | None = None) -> np.ndarray:
    """Finite, positive flux and acceptable quality. bitmask None means any nonzero flag is bad."""
    m = np.isfinite(lc.time) & np.isfinite(lc.flux) & (lc.flux > 0)
    if quality_bitmask is None:
        m &= lc.quality == 0
    else:
        m &= (lc.quality & quality_bitmask) == 0
    return m


def trim_segment_edges(time: np.ndarray, gap_d: float, trim_d: float) -> np.ndarray:
    """Mask the first and last trim_d days of every continuous segment."""
    keep = np.ones(len(time), bool)
    if trim_d <= 0 or len(time) == 0:
        return keep
    breaks = np.where(np.diff(time) > gap_d)[0]
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks, len(time) - 1]
    for s, e in zip(starts, ends, strict=True):
        keep &= ~((time >= time[s]) & (time < time[s] + trim_d))
        keep &= ~((time <= time[e]) & (time > time[e] - trim_d))
    return keep


def prepare(
    lc: LightCurve,
    windows_d: list[float],
    quality_bitmask: int | None = None,
    gap_d: float = 0.5,
    edge_trim_d: float = 0.1,
    flare_clip_sigma: float = 5.0,
    flux: np.ndarray | None = None,
) -> Prepared:
    """Mask, normalize per orbit, clip upward outliers (flares), detrend with biweight.

    `flux` overrides lc.flux (used by injection tests and inverted-flux false-alarm runs).
    """
    raw = lc.flux if flux is None else flux
    m = good_mask(lc, quality_bitmask) & np.isfinite(raw) & (raw > 0)
    t, f, orb = lc.time[m], raw[m].astype(float), lc.orbit[m]
    order = np.argsort(t)
    t, f, orb = t[order], f[order], orb[order]
    for o in np.unique(orb):
        sel = orb == o
        f[sel] = f[sel] / np.nanmedian(f[sel])
    keep = trim_segment_edges(t, gap_d, edge_trim_d)
    t, f = t[keep], f[keep]
    detr = {}
    for w in windows_d:
        trend = flatten(t, f, window_length=w, method="biweight", break_tolerance=gap_d,
                        return_trend=True)[1]
        d = f / trend
        # clip upward outliers only (flares); dips are what we search for
        resid = d - 1.0
        s = robust_std(resid)
        d = np.where(resid > flare_clip_sigma * s, np.nan, d)
        detr[w] = d
    n_masked = int(len(lc.time) - len(t))
    return Prepared(time=t, flux=f, detrended=detr, sector=lc.sector, cadence_s=lc.cadence_s,
                    n_masked=n_masked)
