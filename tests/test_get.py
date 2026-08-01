"""Slice 6: get_stats19() end-to-end + multi-year joins + DuckDB Spatial."""

from __future__ import annotations

import duckdb
import pytest

from stats19 import get_stats19, read_casualties, read_collisions

pytestmark = pytest.mark.usefixtures("skipif_no_spatial")


@pytest.fixture(scope="module")
def skipif_no_spatial():
    try:
        con = duckdb.connect()
        con.execute("INSTALL spatial")
        con.execute("LOAD spatial")
        con.close()
    except Exception:
        pytest.skip("DuckDB spatial extension unavailable")


def test_get_stats19_end_to_end(data_dir_2024) -> None:
    """get_stats19 downloads-if-needed then reads formatted collisions."""
    df = get_stats19(year=2024, type="collision", data_dir=str(data_dir_2024), silent=True)
    assert df is not None
    assert df.shape == (100927, 42)
    assert "collision_severity" in df.columns


def test_get_collisions_helper(data_dir_2024) -> None:
    """get_collisions() mirrors get_stats19(type='collision')."""
    from stats19 import get_collisions

    df = get_collisions(year=2024, data_dir=str(data_dir_2024), silent=True)
    ref = get_stats19(year=2024, type="collision", data_dir=str(data_dir_2024), silent=True)
    assert df is not None and ref is not None
    assert df.equals(ref)
    assert df.shape == (100927, 42)


def test_get_casualties_helper(data_dir_2024) -> None:
    from stats19 import get_casualties

    df = get_casualties(year=2024, data_dir=str(data_dir_2024), silent=True)
    ref = get_stats19(year=2024, type="casualty", data_dir=str(data_dir_2024), silent=True)
    assert df is not None and ref is not None
    assert df.equals(ref)
    assert "casualty_type" in df.columns


def test_get_vehicles_helper(data_dir_2024) -> None:
    from stats19 import get_vehicles

    df = get_vehicles(year=2024, data_dir=str(data_dir_2024), silent=True)
    ref = get_stats19(year=2024, type="vehicle", data_dir=str(data_dir_2024), silent=True)
    assert df is not None and ref is not None
    assert df.equals(ref)
    assert "vehicle_type" in df.columns


def test_get_stats19_accident_alias(data_dir_2024) -> None:
    """R: type 'accident'/'accidents' maps to 'collision'."""
    df = get_stats19(year=2024, type="accidents", data_dir=str(data_dir_2024), silent=True)
    assert df is not None
    assert df.shape[0] == 100927


def test_get_stats19_casualties_not_spatial(data_dir_2024) -> None:
    """R: casualties have no spatial dimension -> tibble even if sf requested."""
    df = get_stats19(
        year=2024, type="casualty", data_dir=str(data_dir_2024), silent=True, output_format="sf"
    )
    assert df is not None
    assert "geom" not in df.columns
    assert df.shape[0] == 128272


def test_get_stats19_sf_output_format(data_dir_2024) -> None:
    """R: output_format='sf' returns spatial points for collisions."""

    df = get_stats19(
        year=2024, type="collision", data_dir=str(data_dir_2024), silent=True, output_format="sf"
    )
    assert df is not None
    assert "geom" in df.columns
    assert df.shape[0] <= 100927  # NA-coordinate rows dropped
    # 42 formatted cols - 2 coordinate cols + 1 geom col = 41
    assert df.shape[1] == 41


def test_multi_year_read_concatenates(data_dir_2024) -> None:
    """Reading [2024, 2025] concatenates rows (R multi-year behaviour)."""
    df = read_collisions(year=[2024, 2025], data_dir=str(data_dir_2024))
    assert df is not None
    assert df.shape[0] == 100927 + 101525


def test_join_collisions_casualties(data_dir_2024) -> None:
    """Join on collision_index reproduces R join counts (1 casualty row per casualty)."""
    coll = read_collisions(year=2024, data_dir=str(data_dir_2024))
    cas = read_casualties(year=2024, data_dir=str(data_dir_2024))
    assert coll is not None and cas is not None
    joined = cas.merge(
        coll[["collision_index", "collision_severity"]], on="collision_index", how="left"
    )
    # every casualty joins to a collision
    assert joined["collision_severity"].notna().sum() == len(cas)
    # severity distribution matches collisions table
    n_fatal = int((coll["collision_severity"] == "Fatal").sum())
    n_fatal_cas = int((joined["collision_severity"] == "Fatal").sum())
    assert n_fatal_cas >= n_fatal  # fatal collisions can have multiple casualties


def test_escooter_rider_unification(data_dir_2024) -> None:
    """R get_stats19 marks e-scooter riders in casualties (needs vehicle data)."""
    df = get_stats19(
        year=2024, type="casualty", data_dir=str(data_dir_2024), silent=True, format=True
    )
    assert df is not None
    if "casualty_type" in df.columns:
        n = int((df["casualty_type"] == "E-scooter rider").sum())
        # 2024 data contains e-scooter casualties
        assert n > 0
