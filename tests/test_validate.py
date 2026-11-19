import numpy as np
import pandas as pd
import pytest

from longshot.validate import (
    far_threshold,
    injection_completeness,
    match_transit,
    predicted_transits,
)


def test_far_threshold_counts_stars_not_events():
    ev = pd.DataFrame({"tic": [1, 1, 2, 3], "snr": [9.0, 12.0, 6.0, 7.5]})
    stars = pd.Series(range(1, 1001))
    thr, curve = far_threshold(ev, stars, max_rate=1e-3)
    # one star (tic 1) reaches 12; allowing 1 star in 1000 means the threshold can be the
    # lowest s where at most one star exceeds: s just above 7.5
    assert thr == pytest.approx(7.6, abs=1e-9)
    assert curve.loc[curve["snr"].sub(12.0).abs().idxmin(), "n_stars_fa"] == 1


def test_predicted_transits_respects_coverage():
    cov = [(100.0, 110.0), (130.0, 140.0)]
    pt = predicted_transits(t0_btjd=105.0, period=10.0, coverage=cov, dur_d=0.2, min_cov=0.5)
    times = [t for t, _ in pt]
    assert times == pytest.approx([105.0, 135.0])


def test_match_transit():
    ev = pd.DataFrame({"t0": [10.0, 10.05, 20.0], "snr": [6.0, 9.0, 15.0]})
    m = match_transit(ev, 10.02, 0.2, 7.0)
    assert m is not None and m["snr"] == 9.0
    assert match_transit(ev, 30.0, 0.2, 7.0) is None


def test_injection_completeness():
    inj = pd.DataFrame({
        "status": ["ok"] * 4, "det_snr": [12, np.nan, 9, 4],
        "snr_expected": [15, 12, 11, 5], "coverage_good": [1, 1, 0.9, 1],
    })
    r = injection_completeness(inj, snr_thr=8, snr_exp_min=10, coverage_min=0.8)
    assert r["n_selected"] == 3 and r["recovered_selected"] == 2
