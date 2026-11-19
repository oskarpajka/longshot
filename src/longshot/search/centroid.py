"""Centroid-motion statistics for single events (D019).

A transit, on the target or on a blended neighbour, changes the flux-weighted centroid in
proportion to the flux change: dx(t) = k * df(t) with one constant k per axis. A moving
object crossing the aperture (an asteroid) makes a flux bump while the centroid moves first
one way and then the other, which no constant k can describe. The "unexplained" statistic
measures centroid motion inside the event box that is not proportional to the flux change,
compared with the same statistic at every other box position of the same duration in that
sector (an empirical null that includes red noise).
"""

from __future__ import annotations

import numpy as np
from wotan import flatten

from longshot.lc.prep import robust_std


def detrend_series(t: np.ndarray, v: np.ndarray, window_d: float, gap_d: float) -> np.ndarray:
    """Residual of a centroid series about a biweight trend (same filter as the flux)."""
    ok = np.isfinite(t) & np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if ok.sum() < 10:
        return out
    off = np.nanmedian(v[ok])
    # wotan expects positive flux-like values; shift to around 1000 and subtract the trend
    trend = flatten(t[ok], v[ok] - off + 1000.0, window_length=window_d, method="biweight",
                    break_tolerance=gap_d, return_trend=True)[1]
    out[ok] = (v[ok] - off + 1000.0) - trend
    return out


def _box_stats(t, xr, yr, fr, sx, sy, tc, dur):
    inn = (np.abs(t - tc) < dur / 2) & np.isfinite(xr) & np.isfinite(yr) & np.isfinite(fr)
    n = int(inn.sum())
    if n < 3:
        return np.nan, np.nan, n
    shift2, unexpl = 0.0, 0.0
    f = fr[inn]
    ff = float(f @ f)
    for r, s in ((xr[inn], sx), (yr[inn], sy)):
        k = float(r @ f) / ff if ff > 0 else 0.0
        unexpl += float(np.sum((r - k * f) ** 2)) / s**2
        shift2 += (float(np.mean(r)) / (s / np.sqrt(n))) ** 2
    return float(np.sqrt(shift2)), unexpl / n, n


def centroid_stats(
    t: np.ndarray, x: np.ndarray, y: np.ndarray, flux_resid: np.ndarray, t0: float,
    dur: float, window_d: float, gap_d: float = 0.5,
) -> dict[str, float]:
    """Return cen_shift (sigma of the mean in-box shift, both axes), cen_unexpl_z (robust z of
    motion not proportional to flux, against all other box positions) and cen_n_null."""
    nan = {"cen_shift": np.nan, "cen_unexpl_z": np.nan, "cen_n_null": 0}
    if len(t) < 50:
        return nan
    xr = detrend_series(t, x, window_d, gap_d)
    yr = detrend_series(t, y, window_d, gap_d)
    sx, sy = robust_std(xr), robust_std(yr)
    if not (np.isfinite(sx) and np.isfinite(sy) and sx > 0 and sy > 0):
        return nan
    shift, unexpl, n_ev = _box_stats(t, xr, yr, flux_resid, sx, sy, t0, dur)
    if not np.isfinite(unexpl):
        return nan
    centers = np.arange(t[0] + dur / 2, t[-1], dur)
    centers = centers[np.abs(centers - t0) > 1.5 * dur]
    null = []
    for tc in centers:
        _, u, n = _box_stats(t, xr, yr, flux_resid, sx, sy, tc, dur)
        if n >= max(3, 0.5 * n_ev) and np.isfinite(u):
            null.append(u)
    null = np.asarray(null)
    if null.size < 10:
        return {"cen_shift": shift, "cen_unexpl_z": np.nan, "cen_n_null": int(null.size)}
    s = robust_std(null)
    z = (unexpl - np.median(null)) / s if s > 0 else np.nan
    return {"cen_shift": shift, "cen_unexpl_z": float(z), "cen_n_null": int(null.size)}
