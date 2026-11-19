"""Per-star processing shared by the search, false-alarm and injection stages.

The same function runs real, inverted and injected light curves, so all three see exactly the
same masking, detrending and search settings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from longshot.data import qlp
from longshot.lc.prep import prepare, robust_std
from longshot.search.single import duration_grid_h, search


@dataclass
class SearchSettings:
    quality_bitmask: int | None
    gap_d: float
    edge_trim_d: float
    flare_clip_sigma: float
    durations_h: np.ndarray
    windows: list[tuple[float, float]]  # (max_duration_h, window_d), ascending
    report_snr: float
    max_events: int
    min_points: int
    min_coverage: float
    bkg_z_max: float | None = None  # scattered-light mask (D018); None = off
    bkg_pad_d: float = 0.0

    @classmethod
    def from_config(cls, c: dict[str, Any]) -> SearchSettings:
        d = c["durations_h"]
        wins = sorted((float(w["max_duration_h"]), float(w["window_d"])) for w in c["windows"])
        return cls(
            quality_bitmask=c.get("quality_bitmask"),
            gap_d=float(c["gap_d"]),
            edge_trim_d=float(c["edge_trim_d"]),
            flare_clip_sigma=float(c["flare_clip_sigma"]),
            durations_h=duration_grid_h(float(d["min"]), float(d["max"]), int(d["n"])),
            windows=wins,
            report_snr=float(c["report_snr"]),
            max_events=int(c["max_events_per_sector"]),
            min_points=int(c["min_points"]),
            min_coverage=float(c["min_coverage"]),
            bkg_z_max=None if c.get("bkg_z_max") is None else float(c["bkg_z_max"]),
            bkg_pad_d=float(c.get("bkg_pad_d", 0.0)),
        )

    def window_for(self, duration_h: float) -> float:
        for max_h, w in self.windows:
            if duration_h <= max_h + 1e-9:
                return w
        raise ValueError(f"no detrending window for duration {duration_h} h")

    @property
    def window_list(self) -> list[float]:
        return sorted({w for _, w in self.windows})


def intervals(time: np.ndarray, cadence_d: float) -> list[tuple[float, float]]:
    """Merge good cadence times into [start, end] intervals (gap > 1.5 cadences splits)."""
    if len(time) == 0:
        return []
    t = np.sort(time)
    br = np.where(np.diff(t) > 1.5 * cadence_d)[0]
    starts = np.r_[t[0], t[br + 1]] - cadence_d / 2
    ends = np.r_[t[br], t[-1]] + cadence_d / 2
    return [(float(a), float(b)) for a, b in zip(starts, ends, strict=True)]


def search_lightcurve(
    lc: qlp.LightCurve,
    s: SearchSettings,
    invert: bool = False,
    flux_override: np.ndarray | None = None,
) -> tuple[list[dict], dict]:
    prep = prepare(
        lc, s.window_list, s.quality_bitmask, s.gap_d, s.edge_trim_d, s.flare_clip_sigma,
        flux=flux_override, invert=invert, bkg_z_max=s.bkg_z_max, bkg_pad_d=s.bkg_pad_d,
    )
    cad_d = lc.cadence_s / 86400.0
    info = {
        "tic": lc.tic, "sector": lc.sector, "camera": lc.camera, "ccd": lc.ccd,
        "cadence_s": lc.cadence_s, "version": lc.version, "timing_suspect": lc.timing_suspect,
        "n_raw": len(lc.time), "n_good": len(prep.time),
        "sigma": robust_std(prep.detrended[s.window_list[0]] - 1.0) if len(prep.time) else np.nan,
        "coverage": intervals(prep.time, cad_d),
    }
    if len(prep.time) < 50:
        return [], info
    events = search(
        prep.time, prep.detrended, lc.cadence_s, s.durations_h, s.window_for,
        report_snr=s.report_snr, max_events=s.max_events, min_points=s.min_points,
        min_coverage=s.min_coverage,
    )
    rows = []
    for rank, e in enumerate(events):
        r = e.as_dict()
        r.update(tic=lc.tic, sector=lc.sector, camera=lc.camera, ccd=lc.ccd, rank=rank,
                 cadence_s=lc.cadence_s, timing_suspect=lc.timing_suspect)
        rows.append(r)
    return rows, info


def search_star(
    tic: int,
    sectors: list[int],
    s: SearchSettings,
    cache: Path = Path("data/qlp"),
    invert: bool = False,
    flux_hook: Callable[[qlp.LightCurve], np.ndarray] | None = None,
    keep_files: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Search every listed sector of one star. With keep_files=False each light curve is
    deleted from the cache after it has been searched (saves disk on the full sample; files
    are always re-downloadable)."""
    all_events, infos = [], []
    for sec in sectors:
        path = qlp.fetch_lightcurve(tic, sec, cache)
        if path is None:
            infos.append({"tic": tic, "sector": sec, "missing": True})
            continue
        try:
            lc = qlp.read_lightcurve(path)
            flux = flux_hook(lc) if flux_hook else None
            ev, info = search_lightcurve(lc, s, invert=invert, flux_override=flux)
        finally:
            if not keep_files:
                Path(path).unlink(missing_ok=True)
        all_events.extend(ev)
        infos.append(info)
    return all_events, infos
