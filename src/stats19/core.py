"""Core engine for stats19: discover, download, read and format STATS19 data.

A single pipeline, driven by the golden schema:

    discover(year, type) -> filenames
    download(filenames)  -> files on disk
    read(paths)          -> raw DataFrame
    format(df, table)    -> labelled, typed DataFrame

This is deliberately smaller and more schema-driven than the R package it
ports (ropensci/stats19 v4.1.0-dev): all code->label lookups, numeric typing
and column metadata come from ``schema.csv`` rather than being hard-coded.
"""

from __future__ import annotations

import os
import re
import urllib.request

import pandas as pd

from stats19 import data

# ---------------------------------------------------------------------------
# Constants (mirror R package behaviour)
# ---------------------------------------------------------------------------

_DATA_DIR_ENV = "STATS19_DOWNLOAD_DIRECTORY"
_DOMAIN = "https://data.dft.gov.uk"
_DIRECTORY = "road-accidents-safety-data"

#: Labels R maps to NA after lookup (schema rows with these labels become NA).
_MISSING_LABELS = (
    "Data missing or out of range",
    "Unknown",
    "Undefined",
    "Code deprecated",
    "Not known",
)

#: Column renames applied for multi-year joins (R ``unify_cols``).
_UNIFY_COLS: dict[str, tuple[str, ...]] = {
    "collision_index": ("accident_index",),
    "collision_year": ("accident_year",),
    "collision_reference": ("accident_reference", "collision_ref_no"),
    "collision_severity": ("accident_severity",),
}

#: Historic columns merged into their modern counterpart (R behaviour).
_HISTORIC_ALIASES: dict[str, str] = {
    "pedestrian_crossing_human_control_historic": "pedestrian_crossing",
}


# ---------------------------------------------------------------------------
# File discovery (R: find_file_name, get_url, get_data_directory)
# ---------------------------------------------------------------------------


def get_data_directory() -> str:
    """Where STATS19 data are stored (env var ``STATS19_DOWNLOAD_DIRECTORY``
    or ``./data`` under cwd, mirroring R)."""
    return os.environ.get(_DATA_DIR_ENV) or os.path.join(os.getcwd(), "data")


def set_data_directory(path: str) -> None:
    os.environ[_DATA_DIR_ENV] = path


def find_file_name(
    years: int | list[int] | str | None = None, type: str | None = None
) -> list[str]:
    """Resolve requested years/types to actual DfT filenames.

    Port of R ``find_file_name()`` (v4.1.0-dev): requests including any year
    < 2021 resolve to the cumulative ``1979-latest`` files; ``"all"`` does the
    same; individual-year files are used only when all years are >= 2021.
    """
    all_files = data.file_names()
    if years is None:
        result = list(all_files)
    elif years == "all":
        result = [f for f in all_files if "1979-latest" in f]
    else:
        years_list = [years] if isinstance(years, int) else list(years)
        result = []
        if any(isinstance(y, int) and y < 2021 for y in years_list):
            result = [f for f in all_files if "1979-latest" in f]
        else:
            for y in years_list:
                if isinstance(y, int) and 2021 <= y <= 2050:
                    result.extend(
                        f
                        for f in all_files
                        if str(y) in f and "1979" not in f and "adjust" not in f
                    )
            if any(y == 5 or y == "5 years" for y in years_list):
                result.extend(f for f in all_files if "last-5-years" in f and "adjust" not in f)

    if type is not None:
        # R: gsub("cas", "ics-cas", type) so "casualty" -> "ics-casualty"
        pattern = type.lower().replace("cas", "ics-cas")
        result = [f for f in result if pattern in f]

    return list(dict.fromkeys(result))  # unique, order-preserving


def list_files(year: int | None = None, table: str | None = None) -> list[str]:
    """Python-idiomatic wrapper: list available files, optionally filtered."""
    return find_file_name(years=year, type=table)


def get_url(file_name: str = "") -> str:
    return f"{_DOMAIN}/{_DIRECTORY}/{file_name}"


def locate_files(
    data_dir: str | None = None,
    type: str | None = None,
    years: int | list[int] | str | None = None,
) -> list[str]:
    """Paths of requested files that exist on disk (R ``locate_files()``)."""
    data_dir = data_dir or get_data_directory()
    return [
        os.path.join(data_dir, f)
        for f in find_file_name(years=years, type=type)
        if os.path.exists(os.path.join(data_dir, f))
    ]


def locate_one_file(
    filename: str | None = None,
    data_dir: str | None = None,
    year: int | None = None,
    type: str | None = None,
) -> str:
    data_dir = data_dir or get_data_directory()
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"No files found under: {data_dir}")
    paths = locate_files(data_dir=data_dir, type=type, years=year)
    if not paths:
        raise FileNotFoundError(f"No files found under: {data_dir}")
    if filename is not None:
        paths = [p for p in paths if filename in os.path.basename(p)]
    return paths[0]


# ---------------------------------------------------------------------------
# Download (R: dl_stats19)
# ---------------------------------------------------------------------------


def dl_stats19(
    year: int | list[int] | str | None = None,
    type: str | None = None,
    data_dir: str | None = None,
    file_name: str | None = None,
    silent: bool = False,
    timeout: int = 600,
) -> str | None:
    """Download STATS19 files for the requested years/type.

    Skips files already present; returns the last saved path (or ``None``).
    """
    data_dir = data_dir or get_data_directory()
    fnames = (
        [file_name]
        if file_name
        else find_file_name(years=year, type=None if type in (None, "all") else type)
    )
    if not fnames:
        if not silent:
            print("No files found. Check the stats19 website on data.gov.uk")
        return None
    if not silent:
        print("Files identified: " + ", ".join(fnames))

    os.makedirs(data_dir, exist_ok=True)
    last: str | None = None
    for f in fnames:
        dest = os.path.join(data_dir, f)
        if os.path.exists(dest):
            if not silent:
                print(f"Data already exists in data_dir, not downloading: {f}")
            last = dest
            continue
        url = get_url(f)
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp, open(dest, "wb") as out:  # noqa: S310
                out.write(resp.read())
            if not silent:
                print(f"Data saved at {dest}")
            last = dest
        except Exception:
            print(f"Failed to download file: {url}")
            if os.path.exists(dest):
                os.remove(dest)
    return last


# ---------------------------------------------------------------------------
# Reading (R: read_stats19)
# ---------------------------------------------------------------------------


def _read_csv(path: str) -> pd.DataFrame:
    """Read one STATS19 CSV like R readr::read_csv(col_types = col_spec()).

    ``-1`` is NA at read time; schema-character columns are read as strings
    (so code lookups match), schema-numeric columns numerically.
    """
    header = pd.read_csv(path, nrows=0).columns.tolist()
    char_vars = data.character_variables()
    num_vars = data.numeric_variables()
    dtype_map: dict[str, object] = {
        col: (str if col in char_vars else float if col in num_vars else None) for col in header
    }
    dtype_map = {k: v for k, v in dtype_map.items() if v is not None}
    return pd.read_csv(
        path,
        na_values=["", "NA", "-1"],
        dtype=dtype_map,  # type: ignore[arg-type]
        low_memory=False,
    )


def read_stats19(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
    type: str = "collision",
    silent: bool = False,
) -> pd.DataFrame | None:
    """Read STATS19 data, optionally formatted (R ``read_stats19``)."""
    data_dir = data_dir or get_data_directory()
    fnames = [filename] if filename else find_file_name(years=year, type=type)
    if not fnames:
        print("No files found.")
        return None
    existing = [p for p in (os.path.join(data_dir, f) for f in fnames) if os.path.exists(p)]
    if not existing:
        print("Files not found on disk.")
        return None

    frames = [_read_csv(p) for p in existing]
    df = frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
    df.columns = format_column_names(list(df.columns))
    df = _normalize_collision_reference(df)

    if format:
        df = format_stats19(df, type=type)
    else:
        for col in data.numeric_variables() & set(df.columns):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # -1 -> NA across all columns (R safety net after formatting)
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].replace("-1", pd.NA)
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].replace(-1, pd.NA)

    # Filter by year (R: skip for 1979/"all"/5/"5 years")
    if year is not None and year not in (5, "5 years", "all", 1979):
        years = [year] if isinstance(year, int) else list(year)
        year_col = next((c for c in df.columns if c in ("accident_year", "collision_year")), None)
        if year_col is not None:
            filtered = df[df[year_col].isin(years)]
            assert isinstance(filtered, pd.DataFrame)
            return filtered
    return df


def _normalize_collision_reference(x: pd.DataFrame) -> pd.DataFrame:
    """collision_ref_no -> collision_reference (R normalize_collision_reference)."""
    return x.rename(columns={"collision_ref_no": "collision_reference"})


def read_collisions(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
    silent: bool = False,
) -> pd.DataFrame | None:
    return read_stats19(year, filename, data_dir, format, "collision", silent)


def read_casualties(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
) -> pd.DataFrame | None:
    return read_stats19(year, filename, data_dir, format, "casualty")


def read_vehicles(
    year: int | list[int] | str | None = None,
    filename: str = "",
    data_dir: str | None = None,
    format: bool = True,
) -> pd.DataFrame | None:
    return read_stats19(year, filename, data_dir, format, "vehicle")


def get_stats19(
    year: int | list[int] | str | None = None,
    type: str | None = None,
    data_dir: str | None = None,
    ask: bool = False,
    silent: bool = False,
    timeout: int = 600,
) -> pd.DataFrame | None:
    """Download then read (R ``get_stats19()``)."""
    data_dir = data_dir or get_data_directory()
    type_arg = type or "collision"
    dl_stats19(year=year, type=type_arg, data_dir=data_dir, silent=silent, timeout=timeout)
    return read_stats19(year=year, data_dir=data_dir, type=type_arg)


# ---------------------------------------------------------------------------
# Formatting (R: format_column_names, format_stats19)
# ---------------------------------------------------------------------------


def format_column_names(column_names: list[str]) -> list[str]:
    """Clean STATS19 column names (R ``format_column_names()``)."""
    x = [c.lower() for c in column_names]
    x = [c.replace(" ", "_") for c in x]
    x = [re.sub(r"\(|\)", "", c) for c in x]
    x = [re.sub(r"1st", "first", c) for c in x]
    x = [re.sub(r"2nd", "second", c) for c in x]
    x = [c.replace("-", "_") for c in x]
    x = [c.replace("?", "") for c in x]
    return x


def format_stats19(x: pd.DataFrame, type: str) -> pd.DataFrame:
    """Format raw STATS19 data: labels, unified columns, types (R format_stats19)."""
    x = x.copy()
    x.columns = format_column_names(list(x.columns))

    # Unify column names for multi-year joins
    for new_name, old_names in _UNIFY_COLS.items():
        for old in old_names:
            if old in x.columns:
                if new_name in x.columns:
                    x[new_name] = x[new_name].fillna(x[old])
                    x = x.drop(columns=[old])
                else:
                    x = x.rename(columns={old: new_name})

    # Code -> label lookups from the golden schema; missing labels -> NA
    # (masking per-variable, dtype-agnostic: columns may be object or pandas
    # StringDtype depending on read path)
    lkps = data.lookups(type)
    for variable, mapping in lkps.items():
        if variable not in x.columns:
            continue
        x[variable] = x[variable].astype(str).map(lambda v: mapping.get(v, v))
        x[variable] = x[variable].where(~x[variable].isin(_MISSING_LABELS))

    # Standardize missing labels across ALL remaining string columns
    # (numeric columns can never contain these strings, so no dtype gate needed)
    for col in x.columns:
        x[col] = x[col].where(~x[col].isin(_MISSING_LABELS))

    # E-scooter unification (R behaviour)
    if "escooter_flag" in x.columns and "vehicle_type" in x.columns:
        is_escooter = x["escooter_flag"] == "Vehicle was an e-scooter"
        x.loc[is_escooter & x["vehicle_type"].isna(), "vehicle_type"] = "E-scooter"

    # Merge historic columns into modern counterparts
    historic = [c for c in x.columns if c.endswith("_historic")]
    for hcol in historic:
        primary = _HISTORIC_ALIASES.get(hcol, hcol[: -len("_historic")])
        if primary in x.columns:
            x[primary] = x[primary].fillna(x[hcol])
            x = x.drop(columns=[hcol])

    # date + time -> datetime (R POSIXct Europe/London)
    if "date" in x.columns:
        x["date"] = pd.to_datetime(x["date"], format="%d/%m/%Y", errors="coerce")
    if "date" in x.columns and "time" in x.columns:
        times = x["time"].astype(str).str.replace(r"\.\d+", "", regex=True)
        x["datetime"] = pd.to_datetime(
            x["date"].dt.strftime("%Y-%m-%d") + " " + times,
            format="%Y-%m-%d %H:%M",
            errors="coerce",
        )

    # Schema-driven numeric coercion
    num_vars = data.numeric_variables()
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
    return format_stats19(x, type="collision")


def format_casualties(x: pd.DataFrame) -> pd.DataFrame:
    return format_stats19(x, type="casualty")


def format_vehicles(x: pd.DataFrame) -> pd.DataFrame:
    return format_stats19(x, type="vehicle")
