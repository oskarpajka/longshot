"""Duotransit linking and period-alias enumeration.

Two single events on the same star with consistent depth and duration may be two transits of
one object. Their separation dT allows periods P_n = dT / n. An alias is ruled out when one of
its predicted transits falls on good data (coverage >= min_coverage of the transit window)
where no matching event was found. Surviving aliases are reported, not ranked (ranking by the
duration/density likelihood happens in the fitting stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Pair:
    tic: int
    t1: float
    t2: float
    sector1: int
    sector2: int
    depth1: float
    depth2: float
    depth_err1: float
    depth_err2: float
    duration1_d: float
    duration2_d: float
    snr1: float
    snr2: float
    aliases_d: list[float] = field(default_factory=list)
    n_aliases_tested: int = 0
    supporting: dict[float, list[float]] = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return self.t2 - self.t1


def covered_fraction(t_mid: float, dur: float, intervals: list[tuple[float, float]]) -> float:
    lo, hi = t_mid - dur / 2, t_mid + dur / 2
    tot = 0.0
    for a, b in intervals:
        tot += max(0.0, min(b, hi) - max(a, lo))
    return tot / dur if dur > 0 else 0.0


def consistent(e1: dict, e2: dict, depth_sigma: float, dur_ratio_max: float) -> bool:
    err = np.hypot(e1["depth_err"], e2["depth_err"])
    if abs(e1["depth"] - e2["depth"]) > depth_sigma * err:
        return False
    r = e1["duration_d"] / e2["duration_d"]
    return 1 / dur_ratio_max <= r <= dur_ratio_max


def enumerate_aliases(
    pair: Pair,
    intervals: list[tuple[float, float]],
    other_events: list[dict],
    p_min_d: float,
    min_coverage: float,
    max_aliases: int = 5000,
) -> Pair:
    """Fill pair.aliases_d with periods P = dT/n >= p_min_d not excluded by the data."""
    dur = 0.5 * (pair.duration1_d + pair.duration2_d)
    tol = max(dur, 1 / 24)
    t_min = min(a for a, _ in intervals) if intervals else pair.t1
    t_max = max(b for _, b in intervals) if intervals else pair.t2
    n_max = int(np.floor(pair.dt / p_min_d))
    surviving = []
    for n in range(1, min(n_max, max_aliases) + 1):
        p = pair.dt / n
        k_lo = int(np.ceil((t_min - pair.t1) / p)) - 1
        k_hi = int(np.floor((t_max - pair.t1) / p)) + 1
        ok = True
        support = []
        for k in range(k_lo, k_hi + 1):
            tk = pair.t1 + k * p
            if abs(tk - pair.t1) < tol or abs(tk - pair.t2) < tol:
                continue
            if covered_fraction(tk, dur, intervals) < min_coverage:
                continue
            hit = [e for e in other_events if abs(e["t0"] - tk) < tol]
            if hit:
                support.append(tk)
                continue
            ok = False
            break
        if ok:
            surviving.append(p)
            if support:
                pair.supporting[p] = support
    pair.aliases_d = surviving
    pair.n_aliases_tested = min(n_max, max_aliases)
    return pair


def link_star(
    tic: int,
    events: list[dict],
    intervals: list[tuple[float, float]],
    snr_min: float,
    depth_sigma: float = 3.0,
    dur_ratio_max: float = 1.5,
    p_min_d: float = 10.0,
    min_coverage: float = 0.5,
    min_separation_d: float = 1.0,
    support_snr_min: float | None = None,
) -> list[Pair]:
    """Form duotransit pairs among a star's events with snr >= snr_min."""
    strong = sorted((e for e in events if e["snr"] >= snr_min), key=lambda e: e["t0"])
    weak_floor = snr_min if support_snr_min is None else support_snr_min
    others_all = [e for e in events if e["snr"] >= weak_floor]
    pairs = []
    for i in range(len(strong)):
        for j in range(i + 1, len(strong)):
            e1, e2 = strong[i], strong[j]
            if e2["t0"] - e1["t0"] < max(min_separation_d, p_min_d):
                continue
            if not consistent(e1, e2, depth_sigma, dur_ratio_max):
                continue
            p = Pair(tic=tic, t1=e1["t0"], t2=e2["t0"], sector1=e1["sector"],
                     sector2=e2["sector"], depth1=e1["depth"], depth2=e2["depth"],
                     depth_err1=e1["depth_err"], depth_err2=e2["depth_err"],
                     duration1_d=e1["duration_d"], duration2_d=e2["duration_d"],
                     snr1=e1["snr"], snr2=e2["snr"])
            others = [e for e in others_all if e is not e1 and e is not e2]
            pairs.append(enumerate_aliases(p, intervals, others, p_min_d, min_coverage))
    return pairs
