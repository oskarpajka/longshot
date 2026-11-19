"""TIC v8.2 target selection through the MAST Catalogs service.

The sample cuts live in the config (configs/targets_mdwarf.yaml), not here. Queries are paged
and each page is cached under data/tic/ so an interrupted run resumes without re-querying.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

KEEP_COLUMNS = [
    "ID", "ra", "dec", "pmRA", "pmDEC", "plx", "e_plx", "Tmag", "e_Tmag", "Teff", "e_Teff",
    "logg", "rad", "e_rad", "mass", "e_mass", "rho", "e_rho", "contratio", "numcont",
    "lumclass", "GAIA", "GAIAmag", "d", "disposition", "duplicate_id", "splists", "version",
]


def _query_page(criteria: dict[str, Any], page: int, pagesize: int, retries: int = 4):
    from astroquery.mast import Catalogs

    for attempt in range(retries):
        try:
            return Catalogs.query_criteria(
                catalog="Tic", pagesize=pagesize, page=page, **criteria
            )
        except Exception:  # network errors from MAST are varied; retry with backoff
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def query_paged(
    criteria: dict[str, Any], cache_dir: Path, pagesize: int = 5000, max_pages: int = 1000
) -> pd.DataFrame:
    """Run a paged TIC criteria query, caching each page as parquet-free CSV."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for page in range(1, max_pages + 1):
        f = cache_dir / f"page_{page:04d}.csv"
        if f.exists():
            df = pd.read_csv(f, dtype={"GAIA": str, "ID": "int64"})
        else:
            tab = _query_page(criteria, page, pagesize)
            cols = [c for c in KEEP_COLUMNS if c in tab.colnames]
            df = tab[cols].to_pandas()
            df.to_csv(f, index=False)
        frames.append(df)
        if len(df) < pagesize:
            break
    else:
        raise RuntimeError(f"hit max_pages={max_pages}; increase it")
    out = pd.concat(frames, ignore_index=True)
    return out


def apply_cuts(df: pd.DataFrame, cuts: dict[str, Any]) -> pd.DataFrame:
    """Re-apply sample cuts locally (defensive: server ranges are inclusive and may differ)."""
    m = pd.Series(True, index=df.index)
    m &= df["Teff"].between(cuts["teff_min"], cuts["teff_max"], inclusive="neither")
    m &= df["rad"] < cuts["rad_max"]
    m &= df["Tmag"] <= cuts["tmag_max"]
    m &= df["contratio"].fillna(0) < cuts["contratio_max"]
    if cuts.get("mass_max") is not None:
        m &= df["mass"].isna() | (df["mass"] < cuts["mass_max"])
    if cuts.get("drop_duplicates", True):
        m &= df["duplicate_id"].isna()
        if "disposition" in df:
            m &= ~df["disposition"].isin(["ARTIFACT", "DUPLICATE", "SPLIT"])
    out = df[m].drop_duplicates("ID").sort_values("ID").reset_index(drop=True)
    return out
