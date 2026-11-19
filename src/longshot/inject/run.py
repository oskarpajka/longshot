"""Injection-recovery: inject one synthetic single transit into a real QLP sector, run the
unchanged search on it, and record whether and how strongly it was recovered.

Injection goes into the raw SAP flux (multiplicative), before our detrending, so the test
covers masking, detrending and search exactly as applied to real data (D011).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from longshot.data import qlp
from longshot.inject.model import REARTH, RSUN, a_over_rs, total_duration_d, transit_flux
from longshot.lc.prep import prepare, robust_std
from longshot.pipeline import SearchSettings, commonmode_keep, search_lightcurve


@dataclass
class Injection:
    inj_id: int
    tic: int
    sector: int
    t0: float
    period_d: float
    rp_earth: float
    b: float
    rstar: float
    mstar: float

    @property
    def k(self) -> float:
        return self.rp_earth * REARTH / (self.rstar * RSUN)


def draw_injections(
    star_sectors: list[tuple[int, int, float, float]],
    n: int,
    rng: np.random.Generator,
    rp_range=(1.0, 15.0),
    p_range=(20.0, 500.0),
    b_max: float = 0.9,
    start_id: int = 0,
) -> list[Injection]:
    """star_sectors rows: (tic, sector, rstar, mstar). t0 is drawn later from the data span."""
    out = []
    idx = rng.integers(0, len(star_sectors), n)
    for j, i in enumerate(idx):
        tic, sec, rs, ms = star_sectors[i]
        out.append(Injection(
            inj_id=start_id + j, tic=int(tic), sector=int(sec), t0=np.nan,
            period_d=float(np.exp(rng.uniform(*np.log(p_range)))),
            rp_earth=float(np.exp(rng.uniform(*np.log(rp_range)))),
            b=float(rng.uniform(0, b_max)), rstar=float(rs), mstar=float(ms),
        ))
    return out


def run_injection(inj: Injection, s: SearchSettings, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    path = qlp.fetch_lightcurve(inj.tic, inj.sector)
    if path is None:
        return {**asdict(inj), "status": "missing"}
    lc = qlp.read_lightcurve(path)
    finite = np.isfinite(lc.time)
    t_lo, t_hi = np.nanmin(lc.time[finite]), np.nanmax(lc.time[finite])
    inj.t0 = float(rng.uniform(t_lo, t_hi))
    aors = a_over_rs(inj.period_d, inj.mstar, inj.rstar)
    k = inj.k
    dur = total_duration_d(inj.period_d, aors, k, inj.b)
    model = np.ones_like(lc.time)
    model[finite] = transit_flux(lc.time[finite], inj.t0, inj.period_d, k, aors, inj.b,
                                 supersample=5 if lc.cadence_s > 300 else 1,
                                 exp_time_d=lc.cadence_s / 86400)
    flux = lc.flux * model

    # Expected SNR on the uninjected, prepared data (white-noise, good cadences only)
    base = prepare(lc, s.window_list, s.quality_bitmask, s.gap_d, s.edge_trim_d,
                   s.flare_clip_sigma, bkg_z_max=s.bkg_z_max, bkg_pad_d=s.bkg_pad_d,
                   bkg_two_sided=s.bkg_two_sided, extra_keep=commonmode_keep(lc, s))
    w = s.window_for(min(max(dur * 24, s.durations_h[0]), s.durations_h[-1]))
    resid = base.detrended[w] - 1.0
    ok = np.isfinite(resid)
    sigma = robust_std(resid[ok])
    tg = base.time[ok]
    in_tr = np.abs(tg - inj.t0) < dur / 2
    n_in = int(in_tr.sum())
    cad_d = lc.cadence_s / 86400
    n_exp = dur / cad_d if dur > 0 else 0
    m_in = np.interp(tg[in_tr], lc.time[finite], model[finite]) if n_in else np.array([])
    mean_depth = float(np.mean(1 - m_in)) if n_in else 0.0
    snr_exp = mean_depth / (sigma / np.sqrt(n_in)) if n_in and sigma > 0 else 0.0
    baseline_ok = True  # D021 diagnostic: out-of-transit data on both sides of the injection
    if s.baseline_min_d is not None:
        b = max(dur, s.baseline_min_d)
        need = s.baseline_coverage * b / cad_d
        n_before = int(((tg >= inj.t0 - dur / 2 - b) & (tg < inj.t0 - dur / 2)).sum())
        n_after = int(((tg >= inj.t0 + dur / 2) & (tg < inj.t0 + dur / 2 + b)).sum())
        baseline_ok = n_before >= need and n_after >= need

    events, _ = search_lightcurve(lc, s, flux_override=flux)
    match = [e for e in events if abs(e["t0"] - inj.t0) < 0.5 * max(dur, 1 / 24)]
    best = max(match, key=lambda e: e["snr"]) if match else None
    return {
        **asdict(inj), "status": "ok", "duration_d": dur, "k": k, "aors": aors,
        "mean_depth": mean_depth, "sigma": sigma, "n_in_good": n_in,
        "coverage_good": n_in / n_exp if n_exp else 0.0, "snr_expected": snr_exp,
        "cadence_s": lc.cadence_s, "baseline_ok": baseline_ok,
        "det_snr": best["snr"] if best else np.nan,
        "det_t0": best["t0"] if best else np.nan,
        "det_duration_d": best["duration_d"] if best else np.nan,
        "det_depth": best["depth"] if best else np.nan,
        "det_rank": best["rank"] if best else -1,
    }
