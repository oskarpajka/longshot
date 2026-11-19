"""Known-asteroid veto (D020).

SkyBoT (IMCCE) lists catalogued asteroids near a position at an epoch, geocentric. TESS is up
to ~0.0025 AU from Earth, which shifts a main-belt asteroid by several arcmin, so candidates
from a wide SkyBoT cone are re-positioned with JPL Horizons as seen from TESS (500@-95).
Time scales: BTJD is TDB; the services are given JD = BTJD + 2457000 directly. The ~69 s
TDB-UTC difference moves an asteroid by well under an arcsecond and is ignored.
"""

from __future__ import annotations

import hashlib
import itertools
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

SKYBOT_URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
JD_OFFSET = 2457000.0
CACHE = Path("data/asteroids")
RS_ARCSEC = 900.0
SEP_MAX_ARCSEC = 42.0
MAG_MARGIN = 1.5


def _get(url: str, params: dict, cache: Path, retries: int = 4) -> str:
    """HTTP GET with an on-disk cache keyed by the full query."""
    q = url + "?" + urllib.parse.urlencode(sorted(params.items()))
    key = hashlib.sha256(q.encode()).hexdigest()
    path = Path(cache) / key[:2] / f"{key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(q, timeout=120) as r:
                txt = r.read().decode("utf-8", errors="replace")
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(path)
            return txt
        except OSError as exc:  # network errors: retry with backoff
            last = exc
            time.sleep(2 ** i)
    raise RuntimeError(f"query failed after {retries} tries: {q}") from last


def parse_skybot(txt: str) -> list[dict]:
    out = []
    for line in txt.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("|")]
        if len(f) < 8:
            continue
        try:
            v = float(f[5])
        except ValueError:
            v = np.nan
        out.append({"num": f[0], "name": f[1], "v": v, "d_geo_arcsec": float(f[7])})
    return out


_NUM = re.compile(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)")


def parse_horizons(txt: str) -> list[tuple[float, float]] | None:
    if "$$SOE" not in txt:
        return None
    body = txt.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    pts = []
    for line in body.strip().splitlines():
        parts = line.split(None, 2)  # date, time, rest
        if len(parts) < 3:
            continue
        m = _NUM.search(parts[2])
        if m:
            pts.append((float(m.group(1)), float(m.group(2))))
    return pts or None


def horizons_command(num: str, name: str) -> str:
    return f"{num};" if num not in ("", "-") else f"DES={name};"


def min_separation_arcsec(ra0: float, dec0: float, pts: list[tuple[float, float]]) -> float:
    """Closest approach of the straight path through pts to (ra0, dec0), tangent-plane."""
    c = np.cos(np.radians(dec0))
    xy = np.array([(((ra - ra0 + 180) % 360 - 180) * c * 3600, (dec - dec0) * 3600)
                   for ra, dec in pts])
    best = float(np.min(np.hypot(xy[:, 0], xy[:, 1])))
    for a, b in itertools.pairwise(xy):
        ab = b - a
        L2 = float(ab @ ab)
        if L2 == 0:
            continue
        s = np.clip(-(a @ ab) / L2, 0.0, 1.0)
        best = min(best, float(np.hypot(*(a + s * ab))))
    return best


def asteroid_veto(
    t0_btjd: float, dur_d: float, depth: float, ra: float, dec: float, tmag: float,
    cache: Path = CACHE, rs_arcsec: float = RS_ARCSEC, sep_max: float = SEP_MAX_ARCSEC,
    mag_margin: float = MAG_MARGIN,
) -> dict:
    """Return veto (bool) and details of the closest qualifying asteroid."""
    res = {"ast_veto": False, "ast_name": "", "ast_v": np.nan, "ast_sep_arcsec": np.nan,
           "ast_n_bright": 0, "ast_unresolved": 0}
    if not (depth > 0 and np.isfinite(tmag)):
        return res
    vmax = tmag - 2.5 * np.log10(depth) + mag_margin
    sky = parse_skybot(_get(SKYBOT_URL, {
        "-ep": f"{t0_btjd + JD_OFFSET:.5f}", "-ra": f"{ra:.6f}", "-dec": f"{dec:.6f}",
        "-rs": f"{rs_arcsec:.0f}", "-mime": "text", "-output": "basic", "-loc": "500",
        "-filter": "0", "-objFilter": "111", "-refsys": "EQJ2000"}, cache))
    bright = [a for a in sky if np.isfinite(a["v"]) and a["v"] <= vmax]
    res["ast_n_bright"] = len(bright)
    jds = [t0_btjd - dur_d / 2, t0_btjd, t0_btjd + dur_d / 2]
    tlist = " ".join(f"'{t + JD_OFFSET:.5f}'" for t in jds)
    for a in bright:
        txt = _get(HORIZONS_URL, {
            "format": "text", "COMMAND": f"'{horizons_command(a['num'], a['name'])}'",
            "EPHEM_TYPE": "OBSERVER", "CENTER": "'500@-95'", "TLIST": tlist,
            "QUANTITIES": "'1'", "ANG_FORMAT": "DEG", "OBJ_DATA": "NO"}, cache)
        pts = parse_horizons(txt)
        if pts is None or len(pts) != len(jds):
            res["ast_unresolved"] += 1
            continue
        sep = min_separation_arcsec(ra, dec, pts)
        if not np.isfinite(res["ast_sep_arcsec"]) or sep < res["ast_sep_arcsec"]:
            res.update(ast_name=a["name"], ast_v=a["v"], ast_sep_arcsec=sep)
    res["ast_veto"] = bool(np.isfinite(res["ast_sep_arcsec"]) and res["ast_sep_arcsec"] <= sep_max)
    return res
