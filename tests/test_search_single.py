import numpy as np
import pytest
from astropy.timeseries import BoxLeastSquares

from longshot.search.single import Event, box_scan, duration_grid_h, search, suppress


def _fake_lc(seed=0, depth=0.004, t0=14.3, dur_h=4.0, cadence_s=600, sigma=0.002):
    rng = np.random.default_rng(seed)
    t = np.arange(0, 27, cadence_s / 86400)
    f = 1 + rng.normal(0, sigma, t.size)
    intr = np.abs(t - t0) < dur_h / 48
    f[intr] -= depth
    return t, f


def test_box_scan_matches_astropy_bls_single_transit():
    """Our depth and snr_white equal astropy BLS depth and depth_snr for one transit."""
    t, f = _fake_lc()
    sigma = 0.002
    dur = 4.0 / 24
    t0g, depth, n_in, _cov, snr_w, valid, _ = box_scan(t, f - 1, dur, 600 / 86400, sigma=sigma)
    i = np.argmax(np.where(valid, snr_w, -np.inf))
    bls = BoxLeastSquares(t, f, dy=np.full_like(t, sigma))
    period = 1000.0  # longer than the baseline: exactly one transit in the data
    st = bls.compute_stats(period, dur, t0g[i])
    # BLS depth is relative to the out-of-transit mean; ours is relative to 1.0
    in_tr = bls.transit_mask(t, period, dur, t0g[i])
    assert in_tr.sum() == n_in[i]
    oot = np.mean(f[~in_tr])
    assert depth[i] == pytest.approx(st["depth"][0] - (oot - 1), rel=1e-6)
    bls_res = bls.power([period], [dur], objective="snr")
    assert snr_w[i] == pytest.approx(depth[i] / (sigma / np.sqrt(n_in[i])), rel=1e-9)
    # BLS depth_snr uses the BLS depth error (sigma / sqrt(n_in) for one transit at long P)
    assert st["depth"][1] == pytest.approx(sigma / np.sqrt(n_in[i]) * np.sqrt(1 + n_in[i] / (len(t) - n_in[i])), rel=1e-3)
    assert bls_res.depth_snr[0] > 0


def test_search_recovers_injected_event():
    t, f = _fake_lc(depth=0.004)
    durs = duration_grid_h(0.5, 12, 12)
    ev = search(t, {1.0: f}, 600, durs, lambda d: 1.0)
    assert ev, "no events"
    best = ev[0]
    assert abs(best.t0 - 14.3) < 2 / 24
    assert 2.0 < best.duration_d * 24 < 7.0
    assert best.depth == pytest.approx(0.004, rel=0.3)
    assert best.snr > 8  # expected 0.004/(0.002/sqrt(24)) = 9.8


def test_search_pure_noise_has_no_strong_events():
    rng = np.random.default_rng(42)
    t = np.arange(0, 27, 600 / 86400)
    f = 1 + rng.normal(0, 0.002, t.size)
    ev = search(t, {1.0: f}, 600, duration_grid_h(0.5, 12, 12), lambda d: 1.0)
    assert all(e.snr < 7 for e in ev)


def test_suppress_keeps_strongest_of_overlapping():
    a = Event(10.0, 0.2, 0.01, 0.001, 12, 12, 20, 1, 1)
    b = Event(10.05, 0.1, 0.01, 0.001, 9, 9, 10, 1, 1)
    c = Event(15.0, 0.1, 0.01, 0.001, 8, 8, 10, 1, 1)
    kept = suppress([b, c, a], 10)
    assert [k.snr for k in kept] == [12, 8]
