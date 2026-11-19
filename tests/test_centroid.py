import numpy as np

from longshot.search.centroid import centroid_stats


def _series(seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(0, 12, 200 / 86400)
    x = 500 + rng.normal(0, 0.01, t.size)
    y = 700 + rng.normal(0, 0.01, t.size)
    f = rng.normal(0, 0.002, t.size)
    return t, x, y, f


def test_transit_with_proportional_centroid_shift_is_explained():
    t, x, y, f = _series()
    inn = np.abs(t - 6.0) < 0.1
    f[inn] -= 0.02
    x[inn] += 0.5 * -0.02  # blended light: shift proportional to flux change
    st = centroid_stats(t, x, y, f, 6.0, 0.2, 0.75)
    assert st["cen_shift"] > 5  # the centroid does move
    assert st["cen_unexpl_z"] < 3  # but the motion is explained by the flux change


def test_moving_object_is_unexplained():
    t, x, y, f = _series(1)
    inn = np.abs(t - 6.0) < 0.1
    phase = (t[inn] - 6.0) / 0.1  # -1 .. 1 across the box
    f[inn] += 0.02 * (1 - phase**2)  # symmetric flux bump
    x[inn] += 0.05 * phase  # centroid sweeps across the aperture
    st = centroid_stats(t, x, y, f, 6.0, 0.2, 0.75)
    assert st["cen_unexpl_z"] > 10


def test_no_centroid_motion_is_quiet():
    t, x, y, f = _series(2)
    f[np.abs(t - 6.0) < 0.1] -= 0.02
    st = centroid_stats(t, x, y, f, 6.0, 0.2, 0.75)
    assert abs(st["cen_unexpl_z"]) < 3 and st["cen_shift"] < 4
