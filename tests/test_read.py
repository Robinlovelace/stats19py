"""Tests for reading STATS19 CSVs into pandas DataFrames (Slice 3).

Ground truth: ropensci/stats19 dev v4.1.0 raw reads (format=FALSE),
captured in scripts/reference/meta_raw_*.
"""

from __future__ import annotations

import csv
import importlib.resources as res
from pathlib import Path

import pandas as pd
import pytest

from stats19 import read

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REF_DIR = Path(__file__).resolve().parents[1] / "scripts" / "reference"

pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "dft-road-casualty-statistics-collision-2024.csv").exists(),
    reason="2024/2025 data not downloaded; run dl_stats19 first",
)


def _raw_meta(table: str, year: int) -> dict:
    """Load the R-captured raw metadata (column names + classes)."""
    path = REF_DIR / f"meta_raw_{table}_{year}.csv"
    with path.open() as f:
        row = next(csv.DictReader(f))
    return row


READERS = {
    "collision": read.read_collisions,
    "casualty": read.read_casualties,
    "vehicle": read.read_vehicles,
}


@pytest.mark.parametrize(
    ("table", "year", "expected_rows", "expected_cols"),
    [
        ("collision", 2024, 100927, 44),
        ("collision", 2025, 101525, 44),
        ("casualty", 2024, 128272, 23),
        ("casualty", 2025, 127883, 23),
        ("vehicle", 2024, 183514, 32),
        ("vehicle", 2025, 183948, 32),
    ],
)
def test_read_rows_and_cols(table: str, year: int, expected_rows: int, expected_cols: int) -> None:
    fn = READERS[table]
    df = fn(year=year, format=False)
    assert len(df) == expected_rows
    assert len(df.columns) == expected_cols


@pytest.mark.parametrize("table", ["collision", "casualty", "vehicle"])
def test_read_column_names_match_r(table: str) -> None:
    """Python column names must exactly match R's raw (format=FALSE) names."""
    meta = _raw_meta(table, 2024)
    r_names = meta["column_names"].split(",")
    df = READERS[table](year=2024, format=False)
    assert list(df.columns) == r_names


@pytest.mark.parametrize("table", ["collision", "casualty", "vehicle"])
def test_read_numeric_columns_are_numeric(table: str) -> None:
    """Columns that R reads as numeric must be numeric in Python."""
    meta = _raw_meta(table, 2024)
    r_names = meta["column_names"].split(",")
    r_classes = meta["classes"].split(",")
    numeric_cols = [n for n, c in zip(r_names, r_classes) if c == "numeric"]
    assert numeric_cols, "expected some numeric columns in reference"

    df = READERS[table](year=2024, format=False)
    for col in numeric_cols:
        assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"


def test_read_uses_data_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STATS19_DOWNLOAD_DIRECTORY", str(tmp_path))
    # Put a tiny csv in place with a recognised filename
    fname = "dft-road-casualty-statistics-collision-2024.csv"
    (tmp_path / fname).write_text(
        "collision_index,collision_year\n2024X001,2024\n", encoding="utf-8"
    )
    df = read.read_collisions(year=2024, format=False, data_dir=str(tmp_path))
    assert len(df) == 1


def test_embedded_schema_loads() -> None:
    """The schema CSV must ship with the package and parse cleanly."""
    path = res.files("stats19").joinpath("data", "stats19_schema.csv")
    with path.open() as f:
        df = pd.read_csv(f)
    assert len(df) == 1820
    assert {"table", "variable", "code", "label"}.issubset(df.columns)
