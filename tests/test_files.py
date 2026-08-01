"""Tests for file discovery and URL construction (Slice 1).

Ground truth: ropensci/stats19 dev version 4.1.0 (PR #316), verified 2026-08-01.
Note: installed CRAN 4.0.0 returns provisional-mid-year-unvalidated 2025 names
that 404 on DfT; the dev version + live DfT return plain -2025.csv names.
"""

from __future__ import annotations

import pytest

import stats19 as files


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (
            2024,
            [
                "dft-road-casualty-statistics-casualty-2024.csv",
                "dft-road-casualty-statistics-vehicle-2024.csv",
                "dft-road-casualty-statistics-collision-2024.csv",
            ],
        ),
        (
            2025,
            [
                "dft-road-casualty-statistics-casualty-2025.csv",
                "dft-road-casualty-statistics-vehicle-2025.csv",
                "dft-road-casualty-statistics-collision-2025.csv",
            ],
        ),
    ],
)
def test_find_file_name_single_year(year: int, expected: list[str]) -> None:
    assert files.find_file_name(year) == expected


def test_find_file_name_all_returns_1979_latest() -> None:
    expected = [
        "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv",
        "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv",
        "dft-road-casualty-statistics-collision-1979-latest-published-year.csv",
    ]
    assert files.find_file_name("all") == expected


def test_find_file_name_pre_2021_uses_1979_latest() -> None:
    """Any request including a year < 2021 resolves to the cumulative file."""
    result = files.find_file_name(2020)
    assert len(result) == 3
    assert all("1979-latest" in f for f in result)


def test_find_file_name_by_type() -> None:
    result = files.find_file_name(2024, type="casualty")
    assert result == ["dft-road-casualty-statistics-casualty-2024.csv"]

    vehicles = files.find_file_name(2024, type="vehicle")
    assert vehicles == ["dft-road-casualty-statistics-vehicle-2024.csv"]


def test_find_file_name_multi_year() -> None:
    result = files.find_file_name([2024, 2025], type="casualty")
    assert result == [
        "dft-road-casualty-statistics-casualty-2024.csv",
        "dft-road-casualty-statistics-casualty-2025.csv",
    ]


def test_get_url() -> None:
    assert files.get_url("dft-road-casualty-statistics-collision-2024.csv") == (
        "https://data.dft.gov.uk/road-accidents-safety-data/"
        "dft-road-casualty-statistics-collision-2024.csv"
    )


def test_list_files_matches_embedded_manifest() -> None:
    """list_files() without args returns the full embedded manifest (26 files)."""
    all_files = files.list_files()
    assert len(all_files) == 26
    assert all(f.endswith(".csv") for f in all_files)


def test_data_directory_roundtrip(tmp_path, monkeypatch) -> None:
    import os

    old = os.environ.get("STATS19_DOWNLOAD_DIRECTORY")
    try:
        files.set_data_directory(str(tmp_path))
        assert files.get_data_directory() == str(tmp_path)
        assert os.environ["STATS19_DOWNLOAD_DIRECTORY"] == str(tmp_path)
    finally:
        if old is None:
            os.environ.pop("STATS19_DOWNLOAD_DIRECTORY", None)
        else:
            os.environ["STATS19_DOWNLOAD_DIRECTORY"] = old


def test_get_data_directory_default(monkeypatch) -> None:
    """Without the env var, defaults to ./data under cwd."""
    import os

    monkeypatch.delenv("STATS19_DOWNLOAD_DIRECTORY", raising=False)
    assert files.get_data_directory() == os.path.join(os.getcwd(), "data")


def test_embedded_data_files_present() -> None:
    """The package must ship the schema and filename data."""
    import importlib.resources as res

    assert res.files("stats19").joinpath("data", "file_names.txt").is_file()
    assert len(files.find_file_name()) == 26
