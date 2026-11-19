"""Load and hash stage configuration files.

Every stage run is driven by one YAML config. The config is stored verbatim in the run
manifest together with a stable hash, so a run can be matched to the exact settings used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a config file is missing required keys or is malformed."""


def load_config(path: str | Path) -> dict[str, Any]:
    """Read a YAML config and check the keys every stage needs."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    for key in ("stage", "run_name"):
        if key not in cfg:
            raise ConfigError(f"{path}: missing required key '{key}'")
    return cfg


def config_hash(cfg: dict[str, Any]) -> str:
    """Stable SHA-256 of a config (key order does not matter)."""
    canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
