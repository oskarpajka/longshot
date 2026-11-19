"""Light curve preparation: masking, normalization and detrending.

We search QLP SAP flux with our own detrending (D011) so that injection-recovery tests pass
through exactly the same processing as the real data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from wotan import flatten

from longshot.data.qlp import LightCurve

MIN_POINTS_TO_DETREND = 10


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


def scattered_light_mask(
    time: np.ndarray, bkg: np.ndarray | None, orbit: np.ndarray, z_max: float | None,
    pad_d: float = 0.0,
) -> np.ndarray:
    """True where the cadence is kept. Drops cadences whose SAP background is more than z_max
    robust sigma above its orbit median, widened by pad_d on each side (D018). Scattered light
    raises the background and leaves ramps in SAP flux that QLP quality flags often miss.
    """
    keep = np.ones(time.size, dtype=bool)
    if z_max is None or bkg is None:
        return keep
    bad = np.zeros(time.size, dtype=bool)
    for o in np.unique(orbit):
        sel = (orbit == o) & np.isfinite(bkg) & np.isfinite(time)
        if sel.sum() < MIN_POINTS_TO_DETREND:
            continue
        b = bkg[sel]
        s = robust_std(b)
        if not np.isfinite(s) or s <= 0:
            continue
        idx = np.flatnonzero(sel)
        bad[idx[(b - np.median(b)) / s > z_max]] = True
    if pad_d > 0 and bad.any():
        tb = np.sort(time[bad & np.isfinite(time)])
        if tb.size:
            j = np.searchsorted(tb, time)
            left = np.abs(time - tb[np.clip(j - 1, 0, tb.size - 1)])
            right = np.abs(tb[np.clip(j, 0, tb.size - 1)] - time)
            bad |= np.minimum(left, right) <= pad_d
    return ~bad


def prepare(
    lc: LightCurve,
    windows_d: list[float],
    quality_bitmask: int | None = None,
    gap_d: float = 0.5,
    edge_trim_d: float = 0.1,
    flare_clip_sigma: float = 5.0,
    flux: np.ndarray | None = None,
    invert: bool = False,
    bkg_z_max: float | None = None,
    bkg_pad_d: float = 0.0,
) -> Prepared:
    """Mask, normalize per orbit, clip upward outliers (flares), detrend with biweight.

    `flux` overrides lc.flux (used by injection tests).
    `invert` mirrors the detrended flux about 1 after flare clipping, for false-alarm
    calibration (D004): real dips become bumps and are not found; noise is unchanged.
    """
    raw = lc.flux if flux is None else flux
    m = good_mask(lc, quality_bitmask) & np.isfinite(raw) & (raw > 0)
    m &= scattered_light_mask(lc.time, lc.bkg, lc.orbit, bkg_z_max, bkg_pad_d)
    t, f, orb = lc.time[m], raw[m].astype(float), lc.orbit[m]
    order = np.argsort(t)
    t, f, orb = t[order], f[order], orb[order]
    for o in np.unique(orb):
        sel = orb == o
        f[sel] = f[sel] / np.nanmedian(f[sel])
    keep = trim_segment_edges(t, gap_d, edge_trim_d)
    t, f = t[keep], f[keep]
    detr = {}
    if len(t) < MIN_POINTS_TO_DETREND:
        # nothing usable in this sector (e.g. every cadence flagged); return empty arrays
        empty = np.array([], dtype=float)
        return Prepared(time=empty, flux=empty, detrended={w: empty for w in windows_d},
                        sector=lc.sector, cadence_s=lc.cadence_s, n_masked=len(lc.time))
    for w in windows_d:
        trend = flatten(t, f, window_length=w, method="biweight", break_tolerance=gap_d,
                        return_trend=True)[1]
        d = f / trend
        # clip upward outliers only (flares); dips are what we search for
        resid = d - 1.0
        s = robust_std(resid)
        d = np.where(resid > flare_clip_sigma * s, np.nan, d)
        detr[w] = 2.0 - d if invert else d
    n_masked = int(len(lc.time) - len(t))
    return Prepared(time=t, flux=f, detrended=detr, sector=lc.sector, cadence_s=lc.cadence_s,
                    n_masked=n_masked)
