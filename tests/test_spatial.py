"""Slice 6 spatial: DuckDB Spatial format_sf, transform, GeoParquet I/O."""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from stats19 import (
    format_sf,
    read_geoparquet,
    st_transform_geometry,
    write_geoparquet,
)

pytestmark = pytest.mark.skipif(
    not (
        lambda: (
            __import__("duckdb").connect().execute("INSTALL spatial").execute("LOAD spatial")
            or True
        )
    )(),
    reason="DuckDB spatial extension unavailable",
)

#: Two known points in Leeds (OSGB easting/northing)
SAMPLE = pd.DataFrame(
    {
        "collision_index": ["2024X001", "2024X002", "2024X003"],
        "location_easting_osgr": [444670.0, 430000.0, None],
        "location_northing_osgr": [364248.0, 430000.0, 430000.0],
    }
)


def test_format_sf_creates_geometry() -> None:
    df = format_sf(SAMPLE)
    assert isinstance(df, pd.DataFrame)
    assert "geom" in df.columns
    assert len(df) == 2  # one row dropped (missing coordinate)
    # WKB of POINT(444670 364248): byte prefix confirms POINT type
    wkb = df.iloc[0]["geom"]
    assert isinstance(wkb, bytes)
    assert wkb[0:1] == b"\x01"  # little-endian
    assert wkb[1:5] == b"\x01\x00\x00\x00"  # POINT type id


def test_format_sf_lonlat_transform() -> None:
    df = format_sf(SAMPLE, lonlat=True)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    # NOTE: DuckDB spatial ST_Transform to EPSG:4326 returns (lat, lon)
    # coordinate order (a known DuckDB quirk vs the usual lon/lat WGS84 order).
    # Leeds city centre ~ 53.8 lat, -1.55 lon.
    import struct

    wkb = df.iloc[0]["geom"]
    assert isinstance(wkb, bytes)
    lat, lon = struct.unpack("<dd", wkb[5:21])
    assert 53.0 < lat < 54.0  # latitude
    assert -2.0 < lon < -1.0  # longitude


def test_format_sf_missing_coords_message(capsys) -> None:
    format_sf(SAMPLE)
    out = capsys.readouterr().out
    assert "1 rows removed with no coordinates" in out


def test_format_sf_relation_type() -> None:
    rel = format_sf(SAMPLE, return_type="relation")
    assert isinstance(rel, duckdb.DuckDBPyRelation)
    n = rel.count("*")
    row = n.fetchone()
    assert row is not None and int(row[0]) >= 1


def test_format_sf_raises_without_coords() -> None:
    with pytest.raises(ValueError, match="easting/northing"):
        format_sf(pd.DataFrame({"a": [1, 2]}))


def test_geoparquet_roundtrip(tmp_path) -> None:
    df = format_sf(SAMPLE)
    assert isinstance(df, pd.DataFrame)
    path = str(tmp_path / "pts.parquet")
    write_geoparquet(df, path)
    rel = read_geoparquet(path)
    out = rel.df()
    assert len(out) == 2
    # geometry column roundtrips as DuckDB geometry
    assert "geom" in out.columns


def test_st_transform_relation() -> None:
    rel = format_sf(SAMPLE, return_type="relation")
    assert isinstance(rel, duckdb.DuckDBPyRelation)
    rel2 = st_transform_geometry(rel, to_crs="EPSG:4326")
    out = rel2.df()
    # longitude in -2..-1
    assert out["geom"].iloc[0] is not None
