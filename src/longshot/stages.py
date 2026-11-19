"""Pipeline stages registered with the CLI. Each stage: (config, manifest) -> status."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from longshot.cli import stage
from longshot.manifest import RunManifest


@stage("targets")
def targets(cfg: dict[str, Any], man: RunManifest) -> str:
    """Build the target list from TIC v8.2 with the configured cuts."""
    from longshot.catalogs import tic

    cuts = cfg["cuts"]
    criteria = {
        "Teff": [cuts["teff_min"], cuts["teff_max"]],
        "rad": [0, cuts["rad_max"]],
        "Tmag": [-5, cuts["tmag_max"]],
        "contratio": [0, cuts["contratio_max"]],
        "objType": "STAR",
    }
    raw = tic.query_paged(criteria, Path(cfg.get("cache_dir", "data/tic/mdwarf")),
                          pagesize=int(cfg.get("pagesize", 5000)))
    man.set_count("tic_rows_raw", len(raw))
    sel = tic.apply_cuts(raw, cuts)
    man.set_count("targets", len(sel))
    man.add_data_version("tic", "TIC v8.2 via MAST Catalogs (astroquery)")
    out = man.run_dir / "targets.csv.gz"
    sel.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})
    man.add_output(out)
    return "ok"


def _latest_run(stage_name: str, run_name: str | None = None, root: Path = Path("results/runs")):
    runs = sorted(p for p in root.glob(f"*_{stage_name}_*") if (p / "manifest.json").exists())
    if run_name:
        runs = [p for p in runs if p.name.endswith(f"_{stage_name}_{run_name}")]
    if not runs:
        raise FileNotFoundError(f"no completed run for stage {stage_name} ({run_name})")
    return runs[-1]


def resolve_run(ref: str, stage_name: str) -> Path:
    """A run reference is either a run directory name or 'latest:<run_name>'."""
    if ref.startswith("latest:"):
        return _latest_run(stage_name, ref.split(":", 1)[1])
    p = Path("results/runs") / ref
    if not (p / "manifest.json").exists():
        raise FileNotFoundError(p)
    return p


@stage("availability")
def availability(cfg: dict[str, Any], man: RunManifest) -> str:
    """Which stars have QLP light curves in which sectors (from QLP target lists)."""
    import pandas as pd

    from longshot.data import qlp

    tdir = resolve_run(cfg["targets_run"], "targets")
    man.add_data_version("targets_run", tdir.name)
    tics = set(pd.read_csv(tdir / "targets.csv.gz", usecols=["ID"])["ID"].astype("int64"))
    tics |= {int(t) for t in cfg.get("extra_tics", [])}
    sectors = list(range(int(cfg["sector_min"]), int(cfg["sector_max"]) + 1))
    av = qlp.availability(tics, sectors)
    found = sorted(av["sector"].unique().tolist())
    man.add_data_version("qlp_sectors_with_target_lists", found)
    man.set_count("stars_requested", len(tics))
    man.set_count("stars_with_qlp", int(av["tic"].nunique()))
    man.set_count("star_sectors", len(av))
    out = man.run_dir / "availability.csv.gz"
    av.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})
    man.add_output(out)
    return "ok"
