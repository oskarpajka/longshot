"""QLP (MIT Quick-Look Pipeline) FFI light curves from MAST.

Availability comes from QLP's per-sector target lists (authoritative list of stars that have a
light curve). Files are cached under data/qlp/ with the same directory layout as MAST, written
atomically, and never committed.

Known product issues (docs/decisions.md D002):
- Sectors 99-104: barycentric timing error in v01 files. Epochs from these sectors are flagged
  (TIMING_SUSPECT_SECTORS) until corrected files are redelivered.
- Column names changed between eras (KSPSAP_FLUX vs DET_FLUX); read_lightcurve normalizes them.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

BASE_URL = "https://archive.stsci.edu/hlsps/qlp"
TIMING_SUSPECT_SECTORS = frozenset(range(99, 105))
VERSIONS = ("v02", "v01")  # newest first: corrected redeliveries use a higher version


def tic16(tic: int) -> str:
    return f"{int(tic):016d}"


def rel_path(tic: int, sector: int, version: str = "v01") -> str:
    t = tic16(tic)
    return (
        f"s{sector:04d}/{t[0:4]}/{t[4:8]}/{t[8:12]}/{t[12:16]}/"
        f"hlsp_qlp_tess_ffi_s{sector:04d}-{t}_tess_{version}_llc.fits"
    )


def _download(url: str, dest: Path, retries: int = 4, timeout: float = 60) -> bool:
    """Download url to dest atomically. Returns False on HTTP 404, raises on other errors."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + f".part{os.getpid()}")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r, tmp.open("wb") as fh:
                while block := r.read(1 << 16):
                    fh.write(block)
            tmp.replace(dest)
            return True
        except urllib.error.HTTPError as exc:
            tmp.unlink(missing_ok=True)
            if exc.code == 404:
                return False
            if attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            tmp.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
        time.sleep(2 ** (attempt + 1))
    return False


def fetch_target_list(sector: int, cache: Path = Path("data/qlp/target_lists")) -> Path:
    dest = Path(cache) / f"s{sector:04d}.csv"
    if not dest.exists():
        ok = _download(f"{BASE_URL}/target_lists/s{sector:04d}.csv", dest)
        if not ok:
            raise FileNotFoundError(f"no QLP target list for sector {sector}")
    return dest


def availability(
    tics: set[int], sectors: list[int], cache: Path = Path("data/qlp/target_lists")
) -> pd.DataFrame:
    """Return rows (tic, sector) for every requested star with a QLP light curve."""
    rows = []
    for s in sectors:
        try:
            path = fetch_target_list(s, cache)
        except FileNotFoundError:
            continue
        ids = pd.read_csv(path, usecols=[0], comment=None, header=0, names=["tic"],
                          dtype={"tic": "int64"}, skiprows=0)
        hit = ids["tic"][ids["tic"].isin(tics)]
        rows.extend((int(t), s) for t in hit.unique())
    return pd.DataFrame(rows, columns=["tic", "sector"]).sort_values(["tic", "sector"],
                                                                     ignore_index=True)


def fetch_lightcurve(tic: int, sector: int, cache: Path = Path("data/qlp")) -> Path | None:
    """Return the cached path of the newest available version, downloading if needed."""
    for v in VERSIONS:
        dest = Path(cache) / rel_path(tic, sector, v)
        if dest.exists():
            return dest
    for v in VERSIONS:
        dest = Path(cache) / rel_path(tic, sector, v)
        if _download(f"{BASE_URL}/{rel_path(tic, sector, v)}", dest):
            return dest
    return None


@dataclass
class LightCurve:
    tic: int
    sector: int
    camera: int
    ccd: int
    time: np.ndarray  # BTJD = BJD_TDB - 2457000
    flux: np.ndarray  # raw SAP flux
    qlp_flux: np.ndarray  # QLP-detrended flux (KSPSAP_FLUX or DET_FLUX)
    qlp_flux_err: np.ndarray
    flux_small: np.ndarray  # QLP detrended, smaller aperture
    flux_large: np.ndarray  # QLP detrended, larger aperture
    quality: np.ndarray
    orbit: np.ndarray
    cadence_s: float
    version: str
    path: str
    meta: dict = field(default_factory=dict)

    @property
    def timing_suspect(self) -> bool:
        return self.sector in TIMING_SUSPECT_SECTORS and self.version == "v01"


def _col(data, *names):
    for n in names:
        if n in data.columns.names:
            return np.asarray(data[n], dtype=float)
    return np.full(len(data), np.nan)


def read_lightcurve(path: Path) -> LightCurve:
    with fits.open(path, memmap=False) as h:
        hd = h[0].header
        d = h[1].data
        t = np.asarray(d["TIME"], dtype=float)
        dt_days = np.nanmedian(np.diff(t)) if len(t) > 1 else np.nan
        version = "v02" if "_v02_" in Path(path).name else "v01"
        return LightCurve(
            tic=int(hd["TICID"]),
            sector=int(hd["SECTOR"]),
            camera=int(hd["CAMERA"]),
            ccd=int(hd["CCD"]),
            time=t,
            flux=_col(d, "SAP_FLUX"),
            qlp_flux=_col(d, "KSPSAP_FLUX", "DET_FLUX"),
            qlp_flux_err=_col(d, "KSPSAP_FLUX_ERR", "DET_FLUX_ERR"),
            flux_small=_col(d, "KSPSAP_FLUX_SML", "DET_FLUX_SML"),
            flux_large=_col(d, "KSPSAP_FLUX_LAG", "DET_FLUX_LAG"),
            quality=np.asarray(d["QUALITY"], dtype=np.int64),
            orbit=np.asarray(d["ORBITID"], dtype=np.int64),
            cadence_s=float(np.round(dt_days * 86400.0)),
            version=version,
            path=str(path),
            meta={k: hd.get(k) for k in ("TESSMAG", "TEFF", "RADIUS", "RA_OBJ", "DEC_OBJ")},
        )
