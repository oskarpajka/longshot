import numpy as np
import pytest

from longshot.search.link import Pair, covered_fraction, enumerate_aliases, link_star


def ev(t0, sector, depth=0.01, err=0.001, dur=0.2, snr=10):
    return {"t0": t0, "sector": sector, "depth": depth, "depth_err": err, "duration_d": dur,
            "snr": snr}


def test_covered_fraction():
    iv = [(0.0, 1.0), (2.0, 3.0)]
    assert covered_fraction(0.5, 0.2, iv) == pytest.approx(1.0)
    assert covered_fraction(1.0, 0.2, iv) == pytest.approx(0.5)
    assert covered_fraction(1.5, 0.2, iv) == 0.0


def test_true_period_survives_and_covered_aliases_are_rejected():
    # True period 50 d; transits at 100 and 300 (dT = 200 = 4 P). Data cover two sectors
    # [90, 117] and [290, 317] plus a sector [190, 217] that contains the predicted transit at
    # 200 (P=50 -> 100, 150, 200, 250, 300): we mark an event there so P=50 is supported.
    iv = [(90.0, 117.0), (190.0, 217.0), (290.0, 317.0)]
    e1, e2, e3 = ev(100.0, 1), ev(300.0, 3), ev(200.0, 2)
    pairs = link_star(1, [e1, e2, e3], iv, snr_min=7, p_min_d=10)
    p13 = next(p for p in pairs if p.t1 == 100.0 and p.t2 == 300.0)
    assert any(abs(a - 50.0) < 1e-9 for a in p13.aliases_d)
    assert any(abs(a - 100.0) < 1e-9 for a in p13.aliases_d)  # 100 -> 200 also supported
    assert any(abs(a - 200.0) < 1e-9 for a in p13.aliases_d)  # no predicted transit in data
    # P = 200/3 = 66.7 predicts 166.7 (gap) and 233.3 (gap): survives; P = 200/19 = 10.5
    # predicts transits inside covered sectors without events: rejected
    assert not any(abs(a - 200 / 19) < 1e-6 for a in p13.aliases_d)


def test_inconsistent_depths_not_linked():
    e1, e2 = ev(100.0, 1, depth=0.01), ev(300.0, 3, depth=0.03)
    assert link_star(1, [e1, e2], [(90, 117), (290, 317)], snr_min=7) == []


def test_enumerate_counts_aliases():
    p = Pair(1, 0.0, 100.0, 1, 2, 0.01, 0.01, 0.001, 0.001, 0.2, 0.2, 10, 10)
    p = enumerate_aliases(p, [(-5.0, 5.0), (95.0, 105.0)], [], p_min_d=10, min_coverage=0.5)
    assert p.n_aliases_tested == 10
    # every alias P = 100/n with n<=10 predicts transits only in the gap (5, 95), except those
    # whose predictions land within the two covered windows
    for a in p.aliases_d:
        n = round(100 / a)
        assert np.isclose(100 / n, a)
