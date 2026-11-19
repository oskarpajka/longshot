"""Phase 1 validation metrics (docs/plan.md section 7, docs/decisions.md D013-D015).

All functions take plain tables so they can be unit tested without network access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from longshot.search.link import covered_fraction


def far_threshold(
    inverted_events: pd.DataFrame,
    stars: pd.Series,
    max_rate: float,
    grid: np.ndarray | None = None,
) -> tuple[float, pd.DataFrame]:
    """Smallest SNR threshold whose per-star false-alarm rate on inverted data <= max_rate.

    Rate(s) = (stars with any inverted event of snr >= s) / (all searched stars).
    """
    grid = np.arange(5.0, 30.01, 0.1) if grid is None else grid
    n = len(stars)
    max_per_star = (
        inverted_events.groupby("tic")["snr"].max().reindex(stars, fill_value=0.0)
        if len(inverted_events) else pd.Series(0.0, index=stars)
    )
    rows = [{"snr": float(s), "n_stars_fa": int((max_per_star >= s).sum()),
             "rate": float((max_per_star >= s).sum() / n)} for s in grid]
    curve = pd.DataFrame(rows)
    ok = curve[curve["rate"] <= max_rate]
    thr = float(ok["snr"].min()) if len(ok) else float("inf")
    return thr, curve


def predicted_transits(
    t0_btjd: float, period: float, coverage: list[tuple[float, float]], dur_d: float,
    min_cov: float,
) -> list[tuple[float, float]]:
    """Predicted mid-times inside the data with coverage fraction >= min_cov."""
    if not coverage:
        return []
    lo = min(a for a, _ in coverage)
    hi = max(b for _, b in coverage)
    n = np.arange(np.ceil((lo - t0_btjd) / period) - 1, np.floor((hi - t0_btjd) / period) + 2)
    out = []
    for tk in t0_btjd + n * period:
        f = covered_fraction(tk, dur_d, coverage)
        if f >= min_cov:
            out.append((float(tk), float(f)))
    return out


def match_transit(
    events: pd.DataFrame, t_pred: float, t14_d: float, snr_thr: float
) -> pd.Series | None:
    """Best event within 0.5 x T14 of the predicted time and above threshold."""
    if not len(events):
        return None
    m = events[(np.abs(events["t0"] - t_pred) < 0.5 * t14_d) & (events["snr"] >= snr_thr)]
    if not len(m):
        return None
    return m.loc[m["snr"].idxmax()]


def injection_completeness(
    inj: pd.DataFrame, snr_thr: float, snr_exp_min: float, coverage_min: float
) -> dict:
    ok = inj[inj["status"] == "ok"].copy()
    ok["recovered"] = ok["det_snr"].fillna(0) >= snr_thr
    sel = ok[(ok["snr_expected"] >= snr_exp_min) & (ok["coverage_good"] >= coverage_min)]
    return {
        "n_ok": len(ok),
        "n_selected": len(sel),
        "recovered_selected": int(sel["recovered"].sum()),
        "fraction_selected": float(sel["recovered"].mean()) if len(sel) else float("nan"),
        "fraction_all": float(ok["recovered"].mean()) if len(ok) else float("nan"),
    }


def completeness_grid(inj: pd.DataFrame, snr_thr: float, rp_bins, p_bins) -> pd.DataFrame:
    ok = inj[inj["status"] == "ok"].copy()
    ok["recovered"] = ok["det_snr"].fillna(0) >= snr_thr
    ok["rp_bin"] = pd.cut(ok["rp_earth"], rp_bins)
    ok["p_bin"] = pd.cut(ok["period_d"], p_bins)
    g = ok.groupby(["rp_bin", "p_bin"], observed=False)["recovered"].agg(["mean", "count"])
    return g.reset_index()


def recovery_by_expected_snr(inj: pd.DataFrame, snr_thr: float, bins) -> pd.DataFrame:
    ok = inj[inj["status"] == "ok"].copy()
    ok["recovered"] = ok["det_snr"].fillna(0) >= snr_thr
    ok["snr_bin"] = pd.cut(ok["snr_expected"], bins)
    return ok.groupby("snr_bin", observed=False)["recovered"].agg(["mean", "count"]).reset_index()
