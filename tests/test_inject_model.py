import numpy as np
import pytest

from longshot.inject.model import a_over_rs, total_duration_d, transit_flux


def test_a_over_rs_earth_sun():
    assert a_over_rs(365.25, 1.0, 1.0) == pytest.approx(215.0, rel=0.01)


def test_duration_earth_sun_central():
    aors = a_over_rs(365.25, 1.0, 1.0)
    k = 6.371e6 / 6.957e8
    assert total_duration_d(365.25, aors, k, 0.0) * 24 == pytest.approx(13.0, rel=0.03)


def test_transit_flux_depth_and_width():
    aors = a_over_rs(100.0, 0.5, 0.5)
    k = 0.1
    t = np.linspace(-1, 1, 20001)
    f = transit_flux(t, 0.0, 100.0, k, aors, 0.0)
    assert 1 - f.min() == pytest.approx(k**2 * 1.2, rel=0.25)  # limb darkening deepens center
    dur = total_duration_d(100.0, aors, k, 0.0)
    intr = t[f < 1]
    assert intr.max() - intr.min() == pytest.approx(dur, rel=0.01)
