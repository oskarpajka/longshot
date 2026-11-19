import numpy as np
import pytest

from longshot.vet import asteroids as A

SKY = """# Flag: 1
# Num | Name | RA(h) | DE(deg) | Class | Mv | Err(arcsec) | d(arcsec) | dRA | dDEC | Dg | Dh
 1170 | Attila | 09 17 09.0 | +13 59 30.0 | MB>Inner | 17.1 | 0.01 | 203.760 | 1 | 1 | 1.5 | 2.4
 - | 2025 MJ372 | 09 17 01.0 | +13 58 00.0 | MB>Inner | 26.1 | 0.4 | 136.640 | 1 | 1 | 1.5 | 2.4
"""
HZ = """header
$$SOE
 2023-Nov-30 01:00:00.000     139.31000  13.99000
 2023-Nov-30 04:48:00.000     139.31341  13.99321
 2023-Nov-30 08:36:00.000 *   139.31700  13.99650
$$EOE
"""


def test_parse_skybot_and_horizons():
    rows = A.parse_skybot(SKY)
    assert [r["name"] for r in rows] == ["Attila", "2025 MJ372"]
    assert rows[0]["v"] == 17.1 and rows[1]["num"] == "-"
    pts = A.parse_horizons(HZ)
    assert len(pts) == 3 and pts[1] == (139.31341, 13.99321)
    assert A.parse_horizons("no ephemeris") is None
    assert A.horizons_command("1170", "Attila") == "1170;"
    assert A.horizons_command("-", "2025 MJ372") == "DES=2025 MJ372;"


def test_min_separation_uses_path_not_only_samples():
    # path passes straight through the target between two samples 100" either side
    pts = [(10.0 - 100 / 3600, 0.0), (10.0 + 100 / 3600, 0.0)]
    assert A.min_separation_arcsec(10.0, 0.0, pts) < 1e-6
    assert abs(A.min_separation_arcsec(10.0, 30 / 3600, pts) - 30) < 1e-6


def test_asteroid_veto_with_canned_services(monkeypatch, tmp_path):
    def fake_get(url, params, cache):
        return SKY if url == A.SKYBOT_URL else HZ

    monkeypatch.setattr(A, "_get", fake_get)
    ra0, dec0 = 139.31341, 13.99321 + 20 / 3600  # 20" from the asteroid track
    r = A.asteroid_veto(3278.2, 0.3, 0.03, ra0, dec0, 13.4, cache=tmp_path)
    assert r["ast_veto"] and r["ast_name"] == "Attila" and r["ast_n_bright"] == 1
    r = A.asteroid_veto(3278.2, 0.3, 0.03, ra0, dec0 + 0.05, 13.4, cache=tmp_path)
    assert not r["ast_veto"]
    # too faint for this depth: 13.4 - 2.5 log10(1e-4) + 1.5 = 24.9 > 17.1, still bright enough;
    # a shallower bright star case: Tmag 8 and depth 0.03 -> vmax 13.3 < 17.1, no candidates
    r = A.asteroid_veto(3278.2, 0.3, 0.03, ra0, dec0, 8.0, cache=tmp_path)
    assert r["ast_n_bright"] == 0 and not r["ast_veto"]
    assert not A.asteroid_veto(3278.2, 0.3, -0.01, ra0, dec0, 13.4, cache=tmp_path)["ast_veto"]


@pytest.mark.network
def test_asteroid_veto_live_known_case(tmp_path):
    """TIC 35285430 S72 inverted false alarm at BTJD 3278.2 (D020): asteroid Attila."""
    r = A.asteroid_veto(3278.2, 4.5 / 24, 0.04, 139.261746, 14.019479, 13.45, cache=tmp_path)
    assert r["ast_veto"] and np.isfinite(r["ast_sep_arcsec"])
