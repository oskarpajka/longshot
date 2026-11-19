import numpy as np
import pandas as pd

from longshot.lc import commonmode as C


def test_star_bins_flags_deviant_hours():
    cad = 600.0
    t = np.arange(1000, 1010, cad / 86400)
    r = np.random.default_rng(0).normal(0, 0.001, t.size)
    r[(t > 1005.0) & (t < 1005.2)] -= 0.01
    b, dev = C.star_bins(t, r, cad)
    assert dev.sum() >= 3
    window = set(range(C.bin_index(np.array([1004.95]))[0],
                       C.bin_index(np.array([1005.25]))[0] + 1))
    assert len(set(b[dev]) & window) >= 3
    assert len(set(b[dev]) - window) <= 1  # ~0.3% of ~240 bins exceed 3 sigma by chance


def test_bad_bins_need_several_stars_and_widen():
    rows = []
    for tic in range(10):
        for b in range(100, 110):
            rows.append({"sector": 86, "camera": 2, "ccd": 3, "tic": tic, "bin": b,
                         "dev": (b == 105 and tic < 3) or (b == 107 and tic == 0)})
    bad = C.bad_bins(pd.DataFrame(rows))
    cam = bad[bad["ccd"] == -1]["bin"].tolist()
    assert cam == [104, 105, 106]  # 3 of 10 stars at bin 105; one star alone is not enough


def test_keep_mask_uses_camera_and_ccd(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"sector": [86, 86], "camera": [2, 2], "ccd": [-1, 3],
                  "bin": [C.bin_index(np.array([3637.3]))[0],
                          C.bin_index(np.array([3640.5]))[0]]}).to_csv(p, index=False)
    t = np.array([3637.3, 3640.5, 3645.0])
    assert C.keep_mask(t, 86, 2, 3, p).tolist() == [False, False, True]
    assert C.keep_mask(t, 86, 2, 1, p).tolist() == [False, True, True]
    assert C.keep_mask(t, 86, 1, 3, p).tolist() == [True, True, True]
    assert C.keep_mask(t, 86, 2, 3, None).all()
