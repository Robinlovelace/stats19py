"""Data layer for stats19: schema, variables and filename manifest.

Everything the engine needs to know about the STATS19 data is loaded here,
from the golden schema (see ``schema.csv`` at the repo root and
``schema_provenance.json`` for provenance).
"""

from __future__ import annotations

import importlib.resources as resources
from functools import lru_cache
from pathlib import Path

import pandas as pd

#: DfT publishes three tables; this is the canonical order.
TABLES = ("collision", "casualty", "vehicle")


@lru_cache(maxsize=1)
def schema() -> pd.DataFrame:
    """Load the golden schema: table/variable/code/label/note/type (1820 rows).

    ``keep_default_na=False`` is critical: the R schema contains the literal
    string ``"None"`` as a label (6 variables, code 0) and pandas would
    otherwise silently convert it to NaN, breaking code->label parity.
    """
    with resources.files("stats19").joinpath("data", "stats19_schema.csv").open() as f:
        return pd.read_csv(f, keep_default_na=False).replace("", pd.NA)


@lru_cache(maxsize=1)
def variables() -> pd.DataFrame:
    """Load per-variable metadata: table/variable/note/type (111 rows)."""
    with resources.files("stats19").joinpath("data", "stats19_variables.csv").open() as f:
        return pd.read_csv(f, keep_default_na=False).replace("", pd.NA)


@lru_cache(maxsize=1)
def file_names() -> list[str]:
    """The manifest of known DfT STATS19 data filenames (26 files)."""
    text = resources.files("stats19").joinpath("data", "file_names.txt").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def lookups(table: str) -> dict[str, dict[str, str]]:
    """Code->label mapping per variable, for one table.

    Example: ``lookups("collision")["light_conditions"]["1"] == "Daylight"``
    """
    s = schema()
    sub = s[(s["table"] == table.lower()) & s["code"].notna()]
    result: dict[str, dict[str, str]] = {}
    for variable, group in sub.groupby("variable"):
        mapping: dict[str, str] = {}
        for _, row in group.iterrows():
            label = row["label"]
            is_missing = label is None or (isinstance(label, float) and pd.isna(label))
            value: str = "" if is_missing else str(label)
            mapping[str(row["code"])] = value
        result[str(variable)] = mapping
    return result


def numeric_variables() -> set[str]:
    """Variables typed numeric/integer in the schema."""
    s = schema()
    return set(s.loc[s["type"].isin(["numeric", "integer"]), "variable"])


def character_variables() -> set[str]:
    """Variables typed character in the schema."""
    s = schema()
    return set(s.loc[s["type"] == "character", "variable"])


def schema_path() -> Path:
    """Path of the golden schema CSV inside the installed package."""
    return Path(str(resources.files("stats19").joinpath("data", "stats19_schema.csv")))
