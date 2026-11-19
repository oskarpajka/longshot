"""Run manifests: results/runs/<run_id>/manifest.json.

A manifest records everything needed to reproduce and audit a stage run: git commit and
dirty flag, the config and its hash, package versions, input data versions, timestamps,
counts, and checksums of output files.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from longshot.config import config_hash

TRACKED_PACKAGES = (
    "longshot",
    "numpy",
    "scipy",
    "pandas",
    "astropy",
    "astroquery",
    "lightkurve",
    "wotan",
    "batman-package",
    "transitleastsquares",
    "triceratops",
    "pytransit",
    "juliet",
    "tess-point",
)


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id(stage: str, run_name: str, when: dt.datetime | None = None) -> str:
    """Run id like 20261119T101500Z_search_pilot. Sortable by time."""
    when = when or dt.datetime.now(dt.UTC)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in run_name)
    return f"{when.strftime('%Y%m%dT%H%M%SZ')}_{stage}_{safe}"


def git_state(repo: Path | None = None) -> dict[str, Any]:
    """Current commit and whether the working tree has uncommitted changes."""
    cwd = str(repo) if repo else None

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain", "--untracked-files=no"))
        branch = run("rev-parse", "--abbrev-ref", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None, "branch": None}
    return {"commit": commit, "dirty": dirty, "branch": branch}


def package_versions(names: tuple[str, ...] = TRACKED_PACKAGES) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


class RunManifest:
    """Collects run metadata and writes manifest.json at the end of a stage."""

    def __init__(self, stage: str, cfg: dict[str, Any], results_root: Path = Path("results/runs")):
        self.stage = stage
        self.cfg = cfg
        self.run_id = make_run_id(stage, str(cfg.get("run_name", "run")))
        self.run_dir = Path(results_root) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.data: dict[str, Any] = {
            "run_id": self.run_id,
            "stage": stage,
            "started_utc": utc_now(),
            "finished_utc": None,
            "status": "running",
            "git": git_state(),
            "config": cfg,
            "config_hash": config_hash(cfg),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": package_versions(),
            "data_versions": {},
            "counts": {},
            "outputs": {},
            "notes": [],
        }

    def set_count(self, key: str, value: float) -> None:
        self.data["counts"][key] = value

    def add_data_version(self, key: str, value: Any) -> None:
        self.data["data_versions"][key] = value

    def add_note(self, text: str) -> None:
        self.data["notes"].append(text)

    def add_output(self, path: Path) -> None:
        """Record an output file inside the run dir with its checksum."""
        full = Path(path).resolve()
        rel = full.relative_to(self.run_dir.resolve())
        self.data["outputs"][rel.as_posix()] = {
            "sha256": sha256_file(full),
            "bytes": full.stat().st_size,
        }

    def finish(self, status: str = "ok") -> Path:
        self.data["finished_utc"] = utc_now()
        self.data["status"] = status
        out = self.run_dir / "manifest.json"
        with out.open("w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")
        return out
