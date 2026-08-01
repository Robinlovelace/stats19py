"""Format STATS19 data: column names, code-to-label lookups, types.

Port of the R package's ``format_column_names()`` and ``format_stats19()``
(v4.1.0-dev).
"""

from __future__ import annotations

import re

import pandas as pd

_MISSING_LABELS = {
    "Data missing or out of range",
    "Unknown",
    "Undefined",
    "Code deprecated",
    "Not known",
}


def format_column_names(column_names: list[str]) -> list[str]:
    """Clean STATS19 column names (R ``format_column_names()``).

    Lowercases, replaces spaces with underscores, strips parentheses,
    expands ordinal prefixes (1st -> first, 2nd -> second), replaces
    hyphens with underscores and removes question marks.
    """
    x = [c.lower() for c in column_names]
    x = [c.replace(" ", "_") for c in x]
    x = [re.sub(r"\(|\)", "", c) for c in x]
    x = [re.sub(r"1st", "first", c) for c in x]
    x = [re.sub(r"2nd", "second", c) for c in x]
    x = [c.replace("-", "_") for c in x]
    x = [c.replace("?", "") for c in x]
    return x


def _unify_columns(x: pd.DataFrame) -> pd.DataFrame:
    """Unify column names for multi-year joins (R ``unify_cols``)."""
    unify = {
        "collision_index": ["accident_index"],
        "collision_year": ["accident_year"],
        "collision_reference": ["accident_reference", "collision_ref_no"],
        "collision_severity": ["accident_severity"],
    }
    for new_name, old_names in unify.items():
        for old_name in old_names:
            if old_name in x.columns:
                if new_name in x.columns:
                    x[new_name] = x[new_name].fillna(x[old_name])
                    x = x.drop(columns=[old_name])
                else:
                    x = x.rename(columns={old_name: new_name})
    return x


def _apply_lookups(x: pd.DataFrame, table: str) -> pd.DataFrame:
    """Replace code columns with labels using the schema (R ``format_stats19``)."""
    from stats19.read import schema

    s = schema()
    lkp_vars = s.loc[s["table"] == table.lower(), "variable"].unique()
    vars_to_change = [v for v in x.columns if v in lkp_vars]
    for v in vars_to_change:
        lookup = s.loc[s["variable"] == v, ["code", "label"]].dropna(subset=["code"])
        if lookup.empty:
            continue
        mapping = dict(zip(lookup["code"].astype(str), lookup["label"]))
        # only replace values present in the lookup; keep others as-is
        x[v] = x[v].astype(str).map(lambda val: mapping.get(val, val))
        x[v] = x[v].where(~x[v].isin(list(_MISSING_LABELS)))
    return x


def _merge_historic(x: pd.DataFrame) -> pd.DataFrame:
    """Merge historic columns into primary columns (R historic unification)."""
    historic_cols = [c for c in x.columns if c.endswith("_historic")]
    for hcol in historic_cols:
        primary = hcol[: -len("_historic")]
        if primary == "pedestrian_crossing_human_control":
            primary = "pedestrian_crossing"
        if primary in x.columns:
            x[primary] = x[primary].fillna(x[hcol])
            x = x.drop(columns=[hcol])
    return x


def format_stats19(x: pd.DataFrame, type: str) -> pd.DataFrame:
    """Format raw STATS19 data (R ``format_stats19()``)."""
    x = x.copy()
    x.columns = format_column_names(list(x.columns))
    x = _unify_columns(x)
    x = _apply_lookups(x, type)

    # Standardize missing labels across ALL string columns
    for col in x.columns:
        if pd.api.types.is_object_dtype(x[col]):
            x[col] = x[col].where(~x[col].isin(list(_MISSING_LABELS)))

    # E-scooter unification
    if "escooter_flag" in x.columns and "vehicle_type" in x.columns:
        is_escooter = x["escooter_flag"] == "Vehicle was an e-scooter"
        x.loc[is_escooter & x["vehicle_type"].isna(), "vehicle_type"] = "E-scooter"

    x = _merge_historic(x)

    # date/time -> datetime (R uses POSIXct Europe/London)
    if "date" in x.columns:
        x["date"] = pd.to_datetime(x["date"], format="%d/%m/%Y", errors="coerce")
    if "date" in x.columns and "time" in x.columns:
        times = x["time"].astype(str).str.replace(r"\.\d+", "", regex=True)
        x["datetime"] = pd.to_datetime(
            x["date"].dt.strftime("%Y-%m-%d") + " " + times,
            format="%Y-%m-%d %H:%M",
            errors="coerce",
        )

    # Numeric coercion per schema
    from stats19.read import schema

    s = schema()
    num_vars = set(s.loc[s["type"].isin(["numeric", "integer"]), "variable"])
    for col in x.columns:
        if col in num_vars:
            x[col] = pd.to_numeric(x[col], errors="coerce")

    # Coordinates to numeric
    coord_re = re.compile(r"easting|northing|latitude|longitude", re.IGNORECASE)
    for col in x.columns:
        if coord_re.search(col):
            x[col] = pd.to_numeric(x[col], errors="coerce")

    return x


def format_collisions(x: pd.DataFrame) -> pd.DataFrame:
    """Format collision data (R ``format_collisions()``)."""
    return format_stats19(x, type="collision")


def format_casualties(x: pd.DataFrame) -> pd.DataFrame:
    """Format casualty data (R ``format_casualties()``)."""
    return format_stats19(x, type="casualty")


def format_vehicles(x: pd.DataFrame) -> pd.DataFrame:
    """Format vehicle data (R ``format_vehicles()``)."""
    return format_stats19(x, type="vehicle")
