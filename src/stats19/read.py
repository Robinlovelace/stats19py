"""Read STATS19 CSV files into pandas DataFrames.

Port of the R package's ``read_collisions()`` / ``read_casualties()`` /
``read_vehicles()`` (v4.1.0-dev). With ``format=False`` the raw columns are
returned (matching R's raw read: modern files already use snake_case names);
with ``format=True`` (default) the formatted output is returned, including
code-to-label lookups — see ``format.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pandas as pd

from stats19.download import ensure_downloaded
from stats19.files import get_data_directory

# Map of R class -> pandas dtype for columns read as numeric by R.
_NUMERIC = "numeric"


def _load_schema() -> pd.DataFrame:
    """Load the embedded STATS19 schema (table/variable/code/label/note/type)."""
    import importlib.resources as res

    with res.files("stats19").joinpath("data", "stats19_schema.csv").open() as f:
        return pd.read_csv(f)


_SCHEMA: pd.DataFrame | None = None


def schema() -> pd.DataFrame:
    """Return the STATS19 schema (cached)."""
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = _load_schema()
    return _SCHEMA


def _read_csv(path: str) -> pd.DataFrame:
    """Read a STATS19 CSV like R's readr::read_csv(col_types = col_spec()).

    Mirrors R v4.1.0-dev: ``-1`` is treated as NA at read time
    (``na = c("", "NA", "-1")``); column types come from the schema where
    known, otherwise pandas type inference (readr ``col_guess()``).
    """
    df = pd.read_csv(path, na_values=["", "NA", "-1"], low_memory=False)
    # Enforce schema-declared numeric/integer types (readr col_spec does this
    # via stats19_variables; we use the same type info from the schema)
    s = schema()
    num_vars = set(s.loc[s["type"].isin(["numeric", "integer"]), "variable"])
    for col in df.columns:
        if col in num_vars and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _coerce_numeric(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Coerce columns R reads as numeric (per captured raw metadata)."""
    s = schema()
    num_vars = set(s.loc[s["type"].isin(["numeric", "integer"]), "variable"])
    # Also handle the *_raw R classes: coordinates etc. are numeric in R
    for col in df.columns:
        if col in num_vars:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _normalize_collision_reference(x: pd.DataFrame) -> pd.DataFrame:
    """Rename collision_ref_no -> collision_reference (R normalize_collision_reference)."""
    if "collision_ref_no" in x.columns:
        x = x.rename(columns={"collision_ref_no": "collision_reference"})
    return x


def read_stats19(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
    type: str = "collision",
    silent: bool = False,
) -> pd.DataFrame | None:
    """Read STATS19 data for the given year/type (R ``read_stats19``)."""
    from stats19.files import find_file_name

    data_dir = data_dir or get_data_directory()
    if filename:
        fnames = [filename]
    else:
        fnames = find_file_name(years=year, type=type)

    if not fnames:
        print("No files found.")
        return None

    paths = [os.path.join(data_dir, f) for f in fnames]
    existing = [p for p in paths if os.path.exists(p)]

    if not existing:
        print("Files not found on disk.")
        return None

    frames = [_read_csv(p) for p in existing]
    if len(frames) == 1:
        df = frames[0]
    else:
        df = pd.concat(frames, ignore_index=True)

    # Column-name normalisation (matches R format_column_names, which is
    # applied even for format=FALSE raw reads in v4.1.0)
    from stats19.format import format_column_names

    df.columns = format_column_names(list(df.columns))

    df = _normalize_collision_reference(df)

    if format:
        from stats19.format import format_stats19

        df = format_stats19(df, type=type)
    else:
        df = _coerce_numeric(df, type)

    # -1 -> NA across all columns (R safety net, applied after formatting)
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].replace("-1", pd.NA)
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].replace(-1, pd.NA)

    # Filter by year if requested (R: skip for 1979/"all"/5/"5 years")
    if year is not None and year not in (5, "5 years", "all", 1979):
        years = [year] if isinstance(year, int) else list(year)
        year_col = next((c for c in df.columns if c in ("accident_year", "collision_year")), None)
        if year_col is not None:
            df = df[df[year_col].isin(years)]
    return df


def read_collisions(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
    silent: bool = False,
) -> pd.DataFrame | None:
    """Read collision data (R ``read_collisions()``)."""
    return read_stats19(
        year=year, filename=filename, data_dir=data_dir, format=format, type="collision"
    )


def read_casualties(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
) -> pd.DataFrame | None:
    """Read casualty data (R ``read_casualties()``)."""
    return read_stats19(
        year=year, filename=filename, data_dir=data_dir, format=format, type="casualty"
    )


def read_vehicles(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
) -> pd.DataFrame | None:
    """Read vehicle data (R ``read_vehicles()``)."""
    return read_stats19(
        year=year, filename=filename, data_dir=data_dir, format=format, type="vehicle"
    )


def get_stats19(
    year: int | list[int] | str | None = None,
    type: str | None = None,
    data_dir: str | None = None,
    ask: bool = False,
    silent: bool = False,
    timeout: int = 600,
) -> pd.DataFrame | None:
    """Download and read STATS19 data in one call (R ``get_stats19()``).

    Downloads any missing files, then reads and formats the requested data.
    """
    data_dir = data_dir or get_data_directory()
    type_arg = type if type is not None else "collision"
    ensure_downloaded(year=year, type=type_arg, data_dir=data_dir, silent=silent, timeout=timeout)
    return read_stats19(year=year, data_dir=data_dir, type=type_arg)
