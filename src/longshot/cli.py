"""Command line entry point: `longshot <stage> --config configs/<x>.yaml`.

Each stage is registered in STAGES. A stage function receives the loaded config and an open
RunManifest, does its work, records counts and outputs, and returns a status string.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from longshot import __version__
from longshot.config import load_config
from longshot.manifest import RunManifest

StageFn = Callable[[dict[str, Any], RunManifest], str]
STAGES: dict[str, StageFn] = {}


def stage(name: str) -> Callable[[StageFn], StageFn]:
    def deco(fn: StageFn) -> StageFn:
        STAGES[name] = fn
        return fn

    return deco


@stage("check-registry")
def _check_registry(cfg: dict[str, Any], man: RunManifest) -> str:
    from longshot import registry

    df = registry.load(Path(cfg.get("registry", registry.DEFAULT_PATH)))
    man.set_count("rows", len(df))
    for status in registry.STATUSES:
        man.set_count(f"status_{status}", int((df["status"] == status).sum()))
    return "ok"


def _load_stage_modules() -> None:
    """Import modules that register further stages (added in later phases)."""
    import importlib

    for mod in ("longshot.stages",):
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError as exc:
            if exc.name != mod:
                raise


def main(argv: list[str] | None = None) -> int:
    _load_stage_modules()
    parser = argparse.ArgumentParser(prog="longshot", description=__doc__)
    parser.add_argument("--version", action="version", version=f"longshot {__version__}")
    parser.add_argument("stage", choices=sorted(STAGES))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--results-root", type=Path, default=Path("results/runs"))
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="run even if code or configs have uncommitted changes (development only)",
    )
    args = parser.parse_args(argv)

    from longshot.manifest import git_state

    if not args.allow_dirty and git_state().get("dirty"):
        parser.error("uncommitted changes in src/configs/tests; commit first or pass --allow-dirty")

    cfg = load_config(args.config)
    if cfg["stage"] != args.stage:
        parser.error(f"config is for stage '{cfg['stage']}', not '{args.stage}'")
    man = RunManifest(args.stage, cfg, results_root=args.results_root)
    try:
        status = STAGES[args.stage](cfg, man)
    except Exception:
        man.finish(status="failed")
        raise
    path = man.finish(status=status)
    print(f"{args.stage}: {status}. manifest: {path}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
