"""Single-event (single transit) search: a box matched filter over epoch and duration.

For each trial duration D and epoch t0 the in-window mean of the detrended residuals gives the
box depth. Two statistics are reported:

- snr_white: depth / (sigma / sqrt(n_in)), sigma the robust scatter of the residuals. This is the
  same quantity astropy BoxLeastSquares calls depth_snr for a single transit with constant
  uncertainties (verified in tests/test_search_single.py).
- snr: snr_white divided by beta_D, the robust standard deviation of the snr_white series over
  all valid epochs for that duration. beta_D absorbs time-correlated (red) noise, so snr is
  comparable across stars and durations. Detection uses snr (threshold set by D004).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from longshot.lc.prep import robust_std


@dataclass
class Event:
    t0: float
    duration_d: float
    depth: float
    depth_err: float
    snr: float
    snr_white: float
    n_in: int
    coverage: float
    beta: float

    def as_dict(self) -> dict:
        return asdict(self)


def duration_grid_h(min_h: float, max_h: float, n: int) -> np.ndarray:
    return np.geomspace(min_h, max_h, n)


def box_scan(
    time: np.ndarray,
    resid: np.ndarray,
    duration_d: float,
    cadence_d: float,
    step_frac: float = 1 / 6,
    min_points: int = 3,
    min_coverage: float = 0.5,
    sigma: float | None = None,
):
    """Scan one duration. Returns (t0_grid, depth, n_in, coverage, snr_white, valid)."""
    ok = np.isfinite(resid) & np.isfinite(time)
    t, r = time[ok], resid[ok]
    order = np.argsort(t)
    t, r = t[order], r[order]
    if sigma is None:
        sigma = robust_std(r)
    step = max(duration_d * step_frac, cadence_d / 2)
    t0 = np.arange(t[0], t[-1] + step, step)
    lo = np.searchsorted(t, t0 - duration_d / 2, side="left")
    hi = np.searchsorted(t, t0 + duration_d / 2, side="left")
    csum = np.r_[0.0, np.cumsum(r)]
    n_in = hi - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (csum[hi] - csum[lo]) / n_in
        depth = -mean
        snr_white = depth / (sigma / np.sqrt(n_in))
    n_exp = duration_d / cadence_d
    coverage = n_in / n_exp
    valid = (n_in >= min_points) & (coverage >= min_coverage)
    return t0, depth, n_in, coverage, snr_white, valid, sigma


def _local_maxima(x: np.ndarray, valid: np.ndarray) -> np.ndarray:
    y = np.where(valid, x, -np.inf)
    left = np.r_[-np.inf, y[:-1]]
    right = np.r_[y[1:], -np.inf]
    return np.where((y >= left) & (y > right) & np.isfinite(y))[0]


def search(
    time: np.ndarray,
    flux_by_window: dict[float, np.ndarray],
    cadence_s: float,
    durations_h: np.ndarray,
    window_for_duration,
    report_snr: float = 5.0,
    max_events: int = 10,
    min_points: int = 3,
    min_coverage: float = 0.5,
    step_frac: float = 1 / 6,
) -> list[Event]:
    """Search one sector. flux_by_window maps detrending window -> detrended flux (~1)."""
    cadence_d = cadence_s / 86400.0
    found: list[Event] = []
    for d_h in durations_h:
        dur = d_h / 24.0
        f = flux_by_window[window_for_duration(d_h)]
        resid = f - 1.0
        t0, depth, n_in, cov, snr_w, valid, sigma = box_scan(
            time, resid, dur, cadence_d, step_frac, min_points, min_coverage
        )
        if valid.sum() < 10:
            continue
        beta = max(1.0, robust_std(snr_w[valid]))
        snr = snr_w / beta
        for i in _local_maxima(snr, valid):
            if snr[i] >= report_snr and depth[i] > 0:
                found.append(Event(
                    t0=float(t0[i]), duration_d=float(dur), depth=float(depth[i]),
                    depth_err=float(beta * sigma / np.sqrt(n_in[i])), snr=float(snr[i]),
                    snr_white=float(snr_w[i]), n_in=int(n_in[i]), coverage=float(cov[i]),
                    beta=float(beta),
                ))
    return suppress(found, max_events)


def suppress(events: list[Event], max_events: int) -> list[Event]:
    """Non-maximum suppression: keep the strongest event among overlapping ones."""
    kept: list[Event] = []
    for e in sorted(events, key=lambda x: -x.snr):
        if all(abs(e.t0 - k.t0) > 0.5 * (e.duration_d + k.duration_d) for k in kept):
            kept.append(e)
        if len(kept) >= max_events:
            break
    return kept
