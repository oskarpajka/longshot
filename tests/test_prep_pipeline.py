import numpy as np
import pytest

from longshot.data.qlp import LightCurve, rel_path
from longshot.lc.prep import prepare, trim_segment_edges
from longshot.pipeline import SearchSettings, intervals, search_lightcurve

SETTINGS = {
    "quality_bitmask": None, "gap_d": 0.5, "edge_trim_d": 0.1, "flare_clip_sigma": 5.0,
    "durations_h": {"min": 0.5, "max": 12.0, "n": 14},
    "windows": [{"max_duration_h": 5.0, "window_d": 0.75},
                {"max_duration_h": 12.0, "window_d": 1.5}],
    "report_snr": 5.0, "max_events_per_sector": 10, "min_points": 3, "min_coverage": 0.5,
}


def fake_lc(depth=0.01, t0=1010.0, dur_d=0.15, sigma=0.002, seed=1, flare_at=None):
    rng = np.random.default_rng(seed)
    cad = 600 / 86400
    t = np.r_[np.arange(1000, 1013, cad), np.arange(1014, 1027, cad)]
    f = 1000 * (1 + 0.003 * np.sin(2 * np.pi * t / 5.0) + rng.normal(0, sigma, t.size))
    f[np.abs(t - t0) < dur_d / 2] *= 1 - depth
    if flare_at is not None:
        f[np.argmin(np.abs(t - flare_at))] *= 1.05
    q = np.zeros(t.size, int)
    q[100:110] = 4096
    orbit = np.where(t < 1013.5, 1, 2)
    nan = np.full(t.size, np.nan)
    return LightCurve(tic=1, sector=40, camera=1, ccd=1, time=t, flux=f, qlp_flux=nan,
                      qlp_flux_err=nan, flux_small=nan, flux_large=nan, quality=q, orbit=orbit,
                      cadence_s=600.0, version="v01", path="x")


def test_rel_path_layout():
    assert rel_path(232608943, 26) == (
        "s0026/0000/0002/3260/8943/hlsp_qlp_tess_ffi_s0026-0000000232608943_tess_v01_llc.fits")


def test_trim_segment_edges():
    t = np.r_[np.arange(0, 1, 0.01), np.arange(2, 3, 0.01)]
    keep = trim_segment_edges(t, 0.5, 0.1)
    assert not keep[t < 0.1].any() and not keep[(t > 0.9) & (t < 1.5)].any()
    assert keep[(t > 0.2) & (t < 0.8)].all()


def test_prepare_masks_quality_and_flattens():
    lc = fake_lc(depth=0.0)
    p = prepare(lc, [0.75])
    assert p.n_masked >= 10
    d = p.detrended[0.75]
    assert np.nanstd(d) < 0.003  # sinusoid removed, noise 0.002 left


def test_flare_is_clipped_not_inverted_into_dip():
    lc = fake_lc(depth=0.0, flare_at=1020.0)
    p = prepare(lc, [0.75], invert=True)
    i = np.argmin(np.abs(p.time - 1020.0))
    assert np.isnan(p.detrended[0.75][i])


def test_search_lightcurve_finds_transit_and_inverted_does_not():
    s = SearchSettings.from_config(SETTINGS)
    lc = fake_lc(depth=0.01)
    ev, info = search_lightcurve(lc, s)
    assert ev and abs(ev[0]["t0"] - 1010.0) < 0.05 and ev[0]["snr"] > 20
    ev_inv, _ = search_lightcurve(lc, s, invert=True)
    assert all(abs(e["t0"] - 1010.0) > 0.1 or e["snr"] < 5 for e in ev_inv)
    assert info["coverage"][0][0] == pytest.approx(1000.1, abs=0.02)


def test_intervals_merge():
    t = np.r_[np.arange(0, 1, 0.1), np.arange(2, 3, 0.1)]
    iv = intervals(t, 0.1)
    assert len(iv) == 2


def test_fully_flagged_sector_returns_empty_not_error():
    lc = fake_lc()
    lc.quality[:] = 4096
    p = prepare(lc, [0.75])
    assert len(p.time) == 0 and len(p.detrended[0.75]) == 0
    s = SearchSettings.from_config(SETTINGS)
    ev, info = search_lightcurve(lc, s)
    assert ev == [] and info["n_good"] == 0


def test_scattered_light_mask_drops_high_background_with_padding():
    from longshot.lc.prep import scattered_light_mask

    t = np.arange(0, 10, 0.01)
    rng = np.random.default_rng(3)
    bkg = 100 + rng.normal(0, 1, t.size)
    bkg[(t > 4.0) & (t < 4.5)] += 50  # scattered-light bump
    orbit = np.ones(t.size, int)
    keep = scattered_light_mask(t, bkg, orbit, z_max=5.0, pad_d=0.2)
    assert not keep[(t > 3.85) & (t < 4.65)].any()
    assert keep[(t < 3.7) | (t > 4.8)].mean() > 0.999
    assert scattered_light_mask(t, bkg, orbit, z_max=None).all()
    assert scattered_light_mask(t, None, orbit, z_max=5.0).all()


def test_prepare_applies_scattered_light_mask():
    lc = fake_lc(depth=0.0)
    bkg = np.full(lc.time.size, 50.0) + np.random.default_rng(0).normal(0, 1, lc.time.size)
    bkg[(lc.time > 1005) & (lc.time < 1006)] += 40
    lc.bkg = bkg
    p0 = prepare(lc, [0.75])
    p1 = prepare(lc, [0.75], bkg_z_max=5.0, bkg_pad_d=0.1)
    assert not ((p1.time > 1005) & (p1.time < 1006)).any()
    assert len(p0.time) - len(p1.time) > 100


def test_scattered_light_mask_two_sided():
    from longshot.lc.prep import scattered_light_mask

    t = np.arange(0, 10, 0.01)
    bkg = 100 + np.random.default_rng(4).normal(0, 1, t.size)
    bkg[(t > 6) & (t < 6.5)] -= 50
    o = np.ones(t.size, int)
    assert scattered_light_mask(t, bkg, o, 5.0)[(t > 6.1) & (t < 6.4)].all()
    assert not scattered_light_mask(t, bkg, o, 5.0, two_sided=True)[(t > 6.1) & (t < 6.4)].any()
