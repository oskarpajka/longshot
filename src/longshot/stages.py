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


def load_search_settings(cfg: dict[str, Any], man: RunManifest) -> dict[str, Any]:
    """Load the shared search settings file and record its full content in the manifest."""
    import yaml

    path = Path(cfg["search_settings"])
    settings = yaml.safe_load(path.read_text())
    man.data["resolved_search_settings"] = {"path": str(path), "settings": settings}
    return settings


def load_targets_file(path: str) -> list[dict]:
    import yaml

    return yaml.safe_load(Path(path).read_text())["targets"]


def _target_pool(targets_ref: str, av, man: RunManifest):
    """Sorted TIC ids that are in the targets run and have QLP data (availability)."""
    import numpy as np
    import pandas as pd

    tdir = resolve_run(targets_ref, "targets")
    man.add_data_version("targets_run", tdir.name)
    pool = pd.read_csv(tdir / "targets.csv.gz", usecols=["ID"])["ID"].astype("int64")
    return np.sort(pool[pool.isin(av["tic"])].to_numpy())


def _draw_sample(smp: dict[str, Any], av, man: RunManifest) -> set[int]:
    """The random calibration draw (D014). Same inputs give the same stars."""
    import numpy as np

    pool = _target_pool(smp["targets_run"], av, man)
    rng = np.random.default_rng(int(smp["seed"]))
    return set(rng.choice(pool, size=int(smp["n"]), replace=False).tolist())


def select_stars(cfg: dict[str, Any], man: RunManifest):
    """Return {tic: [sectors]} for the configured star selection.

    stars.all_targets_run: every target with QLP data (production search).
    stars.sample: a random draw (calibration). stars.exclude_samples: remove those draws.
    stars.include_tics / include_targets_file: add named stars.
    """
    import pandas as pd

    adir = resolve_run(cfg["availability_run"], "availability")
    man.add_data_version("availability_run", adir.name)
    av = pd.read_csv(adir / "availability.csv.gz")
    sel = cfg["stars"]
    chosen: set[int] = set()
    if "all_targets_run" in sel:
        chosen |= {int(t) for t in _target_pool(sel["all_targets_run"], av, man)}
    if "sample" in sel:
        chosen |= _draw_sample(sel["sample"], av, man)
    chosen |= {int(t) for t in sel.get("include_tics", [])}
    if "include_targets_file" in sel:
        chosen |= {int(t["tic"]) for t in load_targets_file(sel["include_targets_file"])}
    excl: set[int] = set()
    for smp in sel.get("exclude_samples", []):
        excl |= _draw_sample(smp, av, man)
    if excl:
        man.set_count("stars_excluded_sample", len(chosen & excl))
        chosen -= excl
    sec_max = int(cfg.get("sector_max", 999))
    av = av[av["tic"].isin(chosen) & (av["sector"] <= sec_max)]
    return {int(t): sorted(g["sector"].tolist()) for t, g in av.groupby("tic")}


def _search_worker(args):
    tic, sectors, settings, invert, keep_files = args
    from longshot.pipeline import SearchSettings, search_star

    s = SearchSettings.from_config(settings)
    try:
        ev, info = search_star(tic, sectors, s, invert=invert, keep_files=keep_files)
        return tic, ev, info, None
    except Exception as exc:  # noqa: BLE001  (recorded per star, never silently dropped)
        return tic, [], [], repr(exc)


def write_table(man: RunManifest, rows: list[dict], name: str, columns=None) -> None:
    import pandas as pd

    df = pd.DataFrame(rows, columns=columns)
    out = man.run_dir / name
    df.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})
    man.add_output(out)


def _checkpoint_dir(cfg: dict[str, Any], man: RunManifest) -> Path | None:
    """Resumable runs: finished chunks are kept under data/checkpoints/<run_name>-<hash>/.

    A checkpoint is reused only by the same config and the same git commit, so a resumed run
    is identical to an uninterrupted one.
    """
    import json

    from longshot.manifest import utc_now

    if not cfg.get("checkpoint", False):
        return None
    commit = man.data["git"].get("commit")
    if commit is None or man.data["git"].get("dirty"):
        raise RuntimeError("checkpointed runs need a clean git checkout")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in cfg["run_name"])
    d = Path(cfg.get("checkpoint_root", "data/checkpoints")) / f"{safe}-{man.data['config_hash'][:12]}"
    d.mkdir(parents=True, exist_ok=True)
    meta = d / "meta.json"
    if meta.exists():
        old = json.loads(meta.read_text(encoding="utf-8"))
        if old.get("git_commit") != commit:
            raise RuntimeError(
                f"checkpoint {d} was made with commit {old.get('git_commit')}, not {commit}. "
                "Delete that folder to start over, or check out the old commit.")
    else:
        meta.write_text(json.dumps({"git_commit": commit, "config_hash": man.data["config_hash"],
                                    "created_utc": utc_now()}, indent=2), encoding="utf-8")
    man.add_data_version("checkpoint_dir", d.as_posix())
    return d


def _save_part(path: Path, tics: list[int], results: list) -> None:
    import gzip
    import os
    import pickle

    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wb") as fh:
        pickle.dump({"tics": tics, "results": results}, fh, protocol=4)
    os.replace(tmp, path)


def _load_part(path: Path, tics: list[int]) -> list:
    import gzip
    import pickle

    with gzip.open(path, "rb") as fh:
        data = pickle.load(fh)  # our own checkpoint files, never downloaded ones
    if data["tics"] != tics:
        raise RuntimeError(f"checkpoint {path} does not match this star list")
    return data["results"]


@stage("search")
def search_stage(cfg: dict[str, Any], man: RunManifest) -> str:
    """Single-event search over a star selection (normal or inverted flux).

    Options for the full sample: keep_lightcurves (default true; false deletes each light curve
    after use), checkpoint (default false; true makes the run resumable), chunk_stars.
    """
    import gzip
    import io
    import json
    from concurrent.futures import ProcessPoolExecutor

    settings = load_search_settings(cfg, man)
    invert = cfg["mode"] == "inverted"
    if cfg["mode"] not in ("normal", "inverted"):
        raise ValueError("mode must be normal or inverted")
    keep_files = bool(cfg.get("keep_lightcurves", True))
    stars = select_stars(cfg, man)
    man.set_count("stars", len(stars))
    man.set_count("star_sectors", sum(len(v) for v in stars.values()))
    pd_stars = [{"tic": t, "n_sectors": len(v), "sectors": " ".join(map(str, v))}
                for t, v in sorted(stars.items())]
    write_table(man, pd_stars, "stars.csv.gz")

    ckdir = _checkpoint_dir(cfg, man)
    chunk = int(cfg.get("chunk_stars", 500))
    workers = int(cfg.get("workers", 4))
    events, infos, errors = [], [], []
    jobs = [(t, v, settings, invert, keep_files) for t, v in sorted(stars.items())]
    cov_path = man.run_dir / "coverage.jsonl.gz"
    n_done = n_resumed = 0
    ex = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        # mtime=0 so identical runs give byte-identical files (checksums in the manifest)
        with gzip.GzipFile(cov_path, "wb", mtime=0) as gz, \
                io.TextIOWrapper(gz, encoding="utf-8") as cov_fh:
            for ci, start in enumerate(range(0, len(jobs), chunk)):
                cjobs = jobs[start:start + chunk]
                tics = [j[0] for j in cjobs]
                part = ckdir / f"part_{ci:05d}.pkl.gz" if ckdir else None
                if part is not None and part.exists():
                    res = _load_part(part, tics)
                    n_resumed += len(res)
                else:
                    mapper = ex.map(_search_worker, cjobs, chunksize=4) if ex else map(
                        _search_worker, cjobs)
                    res = list(mapper)
                    if part is not None:
                        _save_part(part, tics, res)
                for tic, ev, info, err in res:
                    events.extend(ev)
                    for row in info:
                        row = dict(row)
                        cov = row.pop("coverage", None)
                        if cov is not None:
                            cov_fh.write(json.dumps({"tic": tic, "sector": row["sector"],
                                                     "intervals": cov}) + "\n")
                        infos.append(row)
                    if err:
                        errors.append({"tic": tic, "error": err})
                n_done += len(res)
                print(f"  {n_done}/{len(jobs)} stars ({n_resumed} from checkpoint)", flush=True)
    finally:
        if ex is not None:
            ex.shutdown(cancel_futures=True)
    man.add_output(cov_path)
    write_table(man, events, "events.csv.gz")
    write_table(man, infos, "sectors.csv.gz")
    write_table(man, errors, "errors.csv.gz", columns=["tic", "error"])
    man.set_count("events", len(events))
    man.set_count("errors", len(errors))
    man.set_count("stars_from_checkpoint", n_resumed)
    man.set_count("missing_lightcurves", sum(1 for r in infos if r.get("missing")))
    return "ok" if len(errors) <= 0.01 * max(1, len(stars)) else "too_many_errors"


def _inject_worker(args):
    inj, settings, seed = args
    from longshot.inject.run import run_injection
    from longshot.pipeline import SearchSettings

    try:
        return run_injection(inj, SearchSettings.from_config(settings), seed)
    except Exception as exc:  # noqa: BLE001  (recorded per injection)
        from dataclasses import asdict

        return {**asdict(inj), "status": f"error: {exc!r}"}


@stage("inject")
def inject_stage(cfg: dict[str, Any], man: RunManifest) -> str:
    """Injection-recovery on the calibration stars (D004)."""
    from concurrent.futures import ProcessPoolExecutor

    import numpy as np
    import pandas as pd

    from longshot.inject.run import draw_injections

    settings = load_search_settings(cfg, man)
    stars = select_stars(cfg, man)
    tdir = resolve_run(cfg["stars"]["sample"]["targets_run"], "targets")
    tic_tab = pd.read_csv(tdir / "targets.csv.gz", usecols=["ID", "rad", "mass"]).set_index("ID")
    rows = []
    for tic, secs in sorted(stars.items()):
        if tic not in tic_tab.index:
            continue
        rs, ms = tic_tab.loc[tic, "rad"], tic_tab.loc[tic, "mass"]
        if not (np.isfinite(rs) and np.isfinite(ms)):
            continue
        rows.extend((tic, s, float(rs), float(ms)) for s in secs)
    ic = cfg["injections"]
    rng = np.random.default_rng(int(ic["seed"]))
    injs = draw_injections(rows, int(ic["n"]), rng, tuple(ic["rp_earth"]), tuple(ic["period_d"]),
                           float(ic["b_max"]))
    man.set_count("star_sectors_pool", len(rows))
    man.set_count("injections", len(injs))
    seeds = rng.integers(0, 2**31, len(injs))
    jobs = [(inj, settings, int(sd)) for inj, sd in zip(injs, seeds, strict=True)]
    results = []
    with ProcessPoolExecutor(max_workers=int(cfg.get("workers", 4))) as ex:
        for i, r in enumerate(ex.map(_inject_worker, jobs, chunksize=8)):
            results.append(r)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(jobs)} injections", flush=True)
    write_table(man, results, "injections.csv.gz")
    n_err = sum(1 for r in results if str(r.get("status", "")).startswith("error"))
    man.set_count("errors", n_err)
    return "ok" if n_err <= 0.01 * len(results) else "too_many_errors"


def fetch_ephemerides(names: list[str]):
    """Literature parameters from the NASA Exoplanet Archive (pscomppars), fetched live."""
    import io
    import urllib.parse
    import urllib.request

    import pandas as pd

    cols = ("pl_name,tic_id,pl_orbper,pl_orbpererr1,pl_tranmid,pl_tranmiderr1,pl_trandur,"
            "pl_trandep,pl_ratror,pl_ratdor,pl_imppar,pl_rade,st_rad,st_mass,st_teff,sy_tmag")
    q = f"select {cols} from pscomppars where pl_name in (" + ",".join(
        "'" + n.replace("'", "''") + "'" for n in names) + ")"
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode(
        {"query": q, "format": "csv"})
    with urllib.request.urlopen(url, timeout=120) as r:
        return pd.read_csv(io.BytesIO(r.read()))


def _load_run_table(run_dir: Path, name: str):
    import pandas as pd

    return pd.read_csv(run_dir / name)


@stage("validate")
def validate_stage(cfg: dict[str, Any], man: RunManifest) -> str:
    """Score Phase 1 pass criteria. Writes validation.json and summary.md."""
    import gzip
    import json

    import numpy as np
    import pandas as pd

    from longshot import validate as V
    from longshot.inject.model import a_over_rs, transit_flux
    from longshot.search.link import link_star

    crit = cfg["criteria"]
    cfg_targets = load_targets_file(cfg["targets_file"])
    nrun = resolve_run(cfg["search_run"], "search")
    irun = resolve_run(cfg["inverted_run"], "search")
    jrun = resolve_run(cfg["inject_run"], "inject")
    for k, p in (("search_run", nrun), ("inverted_run", irun), ("inject_run", jrun)):
        man.add_data_version(k, p.name)
    for p in (nrun, irun, jrun):
        m = json.loads((p / "manifest.json").read_text())
        if m["status"] != "ok":
            raise RuntimeError(f"input run {p.name} has status {m['status']}")

    # 1. Detection threshold from inverted light curves
    inv = _load_run_table(irun, "events.csv.gz")
    inv_stars = _load_run_table(irun, "stars.csv.gz")["tic"]
    val_tics = {int(t["tic"]) for t in cfg_targets}
    calib_stars = inv_stars[~inv_stars.isin(val_tics)]
    thr, curve = V.far_threshold(inv[inv["tic"].isin(calib_stars)], calib_stars,
                                 float(crit["max_false_alarm_rate"]))
    if "snr_threshold_floor" in crit:
        thr = max(thr, float(crit["snr_threshold_floor"]))
    curve.to_csv(man.run_dir / "far_curve.csv", index=False)
    man.add_output(man.run_dir / "far_curve.csv")

    # 2. Known systems
    ev = _load_run_table(nrun, "events.csv.gz")
    secs = _load_run_table(nrun, "sectors.csv.gz")
    cov: dict[tuple[int, int], list] = {}
    with gzip.open(nrun / "coverage.jsonl.gz", "rt") as fh:
        for line in fh:
            r = json.loads(line)
            cov[(r["tic"], r["sector"])] = [tuple(x) for x in r["intervals"]]
    eph = fetch_ephemerides([t["name"] for t in cfg_targets])
    eph.to_csv(man.run_dir / "ephemerides_nea.csv", index=False)
    man.add_output(man.run_dir / "ephemerides_nea.csv")
    man.add_data_version("nasa_exoplanet_archive", f"pscomppars fetched {man.data['started_utc']}")

    rows, target_rows, duo_rows = [], [], []
    for t in cfg_targets:
        tic, name = int(t["tic"]), t["name"]
        e = eph[eph["pl_name"] == name]
        if not len(e):
            target_rows.append({"name": name, "tic": tic, "status": "no_ephemeris"})
            continue
        e = e.iloc[0]
        P, T0 = float(e.pl_orbper), float(e.pl_tranmid) - 2457000.0
        t14 = float(e.pl_trandur) / 24.0
        k = float(e.pl_ratror) if np.isfinite(e.pl_ratror) else np.sqrt(e.pl_trandep / 100)
        aors = (float(e.pl_ratdor) if np.isfinite(e.pl_ratdor)
                else a_over_rs(P, float(e.st_mass), float(e.st_rad)))
        b = float(e.pl_imppar) if np.isfinite(e.pl_imppar) else 0.3
        star_ev = ev[ev["tic"] == tic]
        star_secs = secs[(secs["tic"] == tic) & ~secs.get("missing", False).fillna(False)]
        n_det = 0
        for _, srow in star_secs.iterrows():
            sec = int(srow["sector"])
            c = cov.get((tic, sec), [])
            for tk, frac in V.predicted_transits(T0, P, c, t14, float(crit["min_coverage"])):
                cad_d = float(srow["cadence_s"]) / 86400
                tt = np.arange(tk - t14 / 2, tk + t14 / 2, cad_d)
                mod = transit_flux(tt, tk, P, k, aors, b)
                n_in = frac * t14 / cad_d
                snr_exp = float(np.mean(1 - mod)) / (float(srow["sigma"]) / np.sqrt(n_in))
                m = V.match_transit(star_ev[star_ev["sector"] == sec], tk, t14, thr)
                row = {"name": name, "tic": tic, "sector": sec, "t_pred": tk, "coverage": frac,
                       "t14_h": t14 * 24, "snr_expected": snr_exp, "detected": m is not None}
                if m is not None:
                    tb = np.linspace(tk - m["duration_d"] / 2, tk + m["duration_d"] / 2, 200)
                    lit_box_depth = float(np.mean(1 - transit_flux(tb, tk, P, k, aors, b)))
                    dur_ratio = m["duration_d"] / t14
                    depth_ok = abs(m["depth"] - lit_box_depth) <= 3 * m["depth_err"]
                    dur_ok = abs(dur_ratio - 1) <= float(crit["duration_tolerance"])
                    epoch_ok = abs(m["t0"] - tk) <= 0.5 * t14
                    row.update(det_t0=m["t0"], det_snr=m["snr"], det_depth=m["depth"],
                               det_depth_err=m["depth_err"], lit_box_depth=lit_box_depth,
                               det_duration_h=m["duration_d"] * 24, duration_ratio=dur_ratio,
                               epoch_ok=epoch_ok, depth_ok=depth_ok, duration_ok=dur_ok,
                               passes=bool(epoch_ok and depth_ok and dur_ok))
                    n_det += int(row["passes"])
                rows.append(row)
        target_rows.append({"name": name, "tic": tic, "period_d": P, "t14_h": t14 * 24,
                            "n_transits_in_data": sum(r["tic"] == tic and r["name"] == name
                                                      for r in rows),
                            "n_transits_passing": n_det, "recovered": n_det >= 1})
        # duotransit check: link detected events of this star, true period among aliases?
        if n_det >= 2:
            all_cov = [iv for (tt_, _), ivs in cov.items() if tt_ == tic for iv in ivs]
            pairs = link_star(tic, star_ev.to_dict("records"), all_cov, snr_min=thr,
                              p_min_d=float(crit["link_p_min_d"]),
                              min_coverage=float(crit["min_coverage"]))
            for pr in pairs:
                near = [a for a in pr.aliases_d if abs(a - P) / P < 0.5 * t14 / pr.dt + 1e-3]
                truth_pair = (abs(((pr.t1 - T0) / P) - round((pr.t1 - T0) / P)) * P < t14
                              and abs(((pr.t2 - T0) / P) - round((pr.t2 - T0) / P)) * P < t14)
                duo_rows.append({"name": name, "t1": pr.t1, "t2": pr.t2, "dt": pr.dt,
                                 "n_aliases": len(pr.aliases_d), "true_pair": truth_pair,
                                 "true_period_in_aliases": bool(near)})
    trans = pd.DataFrame(rows)
    targ = pd.DataFrame(target_rows)
    duo = pd.DataFrame(duo_rows, columns=["name", "t1", "t2", "dt", "n_aliases", "true_pair",
                                          "true_period_in_aliases"])
    for df, fn in ((trans, "known_transits.csv"), (targ, "known_targets.csv"),
                   (duo, "known_duotransits.csv")):
        df.to_csv(man.run_dir / fn, index=False)
        man.add_output(man.run_dir / fn)

    # 3. Injection-recovery
    inj = _load_run_table(jrun, "injections.csv.gz")
    comp = V.injection_completeness(inj, thr, float(crit["inj_snr_expected_min"]),
                                    float(crit["inj_coverage_min"]))
    V.recovery_by_expected_snr(inj, thr, [0, 5, 7, 8, 9, 10, 12, 15, 20, 30, 50, 1e9]).to_csv(
        man.run_dir / "recovery_vs_snr.csv", index=False)
    V.completeness_grid(inj, thr, [1, 2, 3, 4, 6, 8, 11, 15],
                        [20, 40, 80, 160, 320, 500]).to_csv(
        man.run_dir / "completeness_grid.csv", index=False)
    for fn in ("recovery_vs_snr.csv", "completeness_grid.csv"):
        man.add_output(man.run_dir / fn)

    # 4. Verdict
    n_rec = int(targ.get("recovered", pd.Series(dtype=bool)).fillna(False).sum())
    true_duos = duo[duo["true_pair"]] if len(duo) else duo
    far_rate = float(curve.loc[curve["snr"].sub(thr).abs().idxmin(), "rate"])
    checks = {
        "c1_known_recovered": {"value": n_rec, "required": int(crit["min_known_recovered"]),
                               "pass": n_rec >= int(crit["min_known_recovered"])},
        "c2_duo_true_period_in_aliases": {
            "value": f"{int(true_duos['true_period_in_aliases'].sum())}/{len(true_duos)}",
            "pass": bool(len(true_duos) == 0 or true_duos["true_period_in_aliases"].all())},
        "c3_injection_completeness": {
            "value": comp["fraction_selected"], "required": float(crit["inj_min_fraction"]),
            "n": comp["n_selected"], "n_injections_ok": comp["n_ok"],
            "pass": bool(comp["n_ok"] >= int(crit["inj_min_n"])
                         and comp["fraction_selected"] >= float(crit["inj_min_fraction"]))},
        "c4_false_alarm_rate": {"value": far_rate, "threshold_snr": thr,
                                "required": float(crit["max_false_alarm_rate"]),
                                "n_calibration_stars": len(calib_stars),
                                "pass": bool(np.isfinite(thr) and far_rate
                                             <= float(crit["max_false_alarm_rate"]))},
        "c5_reproducibility": {"value": "checked separately by reproducibility-checker",
                               "pass": None},
    }
    verdict = all(c["pass"] for k, c in checks.items() if c["pass"] is not None)
    out = {"snr_threshold": thr, "checks": checks, "pass_c1_to_c4": verdict,
           "injection": comp}
    (man.run_dir / "validation.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    man.add_output(man.run_dir / "validation.json")
    lines = [f"# Phase 1 validation ({man.run_id})", "",
             f"Detection threshold (SNR): {thr:.2f}", ""]
    lines += [f"- {k}: value={c['value']} pass={c['pass']}" for k, c in checks.items()]
    lines += ["", "## Known systems", "", targ.to_markdown(index=False) if len(targ) else "none"]
    (man.run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    man.add_output(man.run_dir / "summary.md")
    man.set_count("known_recovered", n_rec)
    man.data["snr_threshold"] = thr
    return "ok"
