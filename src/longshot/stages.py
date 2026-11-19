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
