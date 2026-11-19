"""Candidate registry: candidates/registry.csv is the single source of truth for every signal.

All writes go through this module, which enforces the column schema and the allowed status
values, so the file cannot silently drift.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = [
    "id",
    "tic",
    "sectors",
    "epochs_btjd",
    "depth_ppm",
    "depth_err_ppm",
    "duration_h",
    "snr",
    "period_est_d",
    "period_aliases_d",
    "tmag",
    "teff",
    "product",
    "status",
    "rejection_reason",
    "report_path",
    "run_id",
    "date_added",
    "date_updated",
]

STATUSES = ("signal", "rejected", "candidate", "vetted", "submitted", "toi")

DEFAULT_PATH = Path("candidates/registry.csv")


class RegistryError(ValueError):
    pass


def empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


def load(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    if not Path(path).exists():
        return empty()
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate(df)
    return df


def validate(df: pd.DataFrame) -> None:
    if list(df.columns) != COLUMNS:
        raise RegistryError(f"registry columns differ from schema: {list(df.columns)}")
    if df["id"].duplicated().any():
        dups = df.loc[df["id"].duplicated(), "id"].tolist()
        raise RegistryError(f"duplicate ids: {dups}")
    bad = sorted(set(df["status"]) - set(STATUSES))
    if bad:
        raise RegistryError(f"unknown status values: {bad}")
    rej = df[(df["status"] == "rejected") & (df["rejection_reason"].astype(str).str.strip() == "")]
    if len(rej):
        raise RegistryError(f"rejected rows without a reason: {rej['id'].tolist()}")


def save(df: pd.DataFrame, path: Path = DEFAULT_PATH) -> None:
    df = df.reindex(columns=COLUMNS).fillna("")
    validate(df)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.sort_values("id").to_csv(path, index=False)


def upsert(df: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    """Insert new rows or update existing ones by id. Unknown keys are an error."""
    df = df.copy()
    for row in rows:
        extra = set(row) - set(COLUMNS)
        if extra:
            raise RegistryError(f"unknown registry fields: {sorted(extra)}")
        if "id" not in row:
            raise RegistryError("row has no id")
        row = {k: ("" if v is None else str(v)) for k, v in row.items()}
        mask = df["id"] == row["id"]
        if mask.any():
            for k, v in row.items():
                df.loc[mask, k] = v
        else:
            full = {c: "" for c in COLUMNS} | row
            df = pd.concat([df, pd.DataFrame([full])], ignore_index=True)
    validate(df)
    return df
