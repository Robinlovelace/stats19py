"""Spatial functions for stats19, backed by DuckDB Spatial (not geopandas).

Port of R ``format_sf()``: converts STATS19 tabular data to spatial points
using the OSGB36 / British National Grid (EPSG:27700) easting/northing
columns, with optional transform to lon/lat (EPSG:4326).

Unlike the R package (which uses the ``sf`` package), this module uses
DuckDB's spatial extension: geometries are created with ``ST_Point`` and
returned as a DuckDB relation (or DataFrame of WKB). This keeps the engine
lightweight and DuckDB-native.
"""

from __future__ import annotations

from typing import Literal

import duckdb
import pandas as pd

#: CRS identifiers used by DuckDB spatial's ST_Transform.
_CRS_OSGB = "EPSG:27700"  # British National Grid (easting/northing)
_CRS_WGS84 = "EPSG:4326"  # lon/lat


def _coordinate_columns(x: pd.DataFrame) -> list[str]:
    """Find easting/northing column names (R: grep 'easting|northing')."""
    return [c for c in x.columns if "easting" in c.lower() or "northing" in c.lower()]


def format_sf(
    x: pd.DataFrame,
    lonlat: bool = False,
    return_type: Literal["relation", "dataframe", "wkb"] = "dataframe",
) -> duckdb.DuckDBPyRelation | pd.DataFrame:
    """Convert STATS19 data to spatial points (R ``format_sf()``).

    Args:
        x: STATS19 DataFrame with easting/northing columns (e.g. collisions).
        lonlat: if True, transform geometry from EPSG:27700 to EPSG:4326.
        return_type:
            - ``"dataframe"`` (default): DataFrame with a ``geom`` WKB column
            - ``"relation"``: DuckDB relation (register in-memory) with geom
            - ``"wkb"``: DataFrame with raw WKB bytes in ``geom``

    Returns:
        Spatial DataFrame/relation; rows with missing coordinates are dropped
        (a message reports how many, mirroring R).
    """
    coords = _coordinate_columns(x)
    if len(coords) < 2:
        raise ValueError("No easting/northing columns found for spatial conversion")
    easting_col, northing_col = coords[0], coords[1]

    coord_null = x[[easting_col, northing_col]].isna().any(axis=1)
    coord_null = coord_null.fillna(False).astype(bool)  # type: ignore[union-attr]
    n_null = int(sum(coord_null.tolist()))
    if n_null > 0:
        print(f"{n_null} rows removed with no coordinates")
    x = x.loc[~coord_null].copy()

    con = duckdb.connect()
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    con.register("stats19_spatial", x)

    geom_expr = f"ST_Point({easting_col}, {northing_col})"
    if lonlat:
        geom_expr = (
            f"ST_Transform(ST_Point({easting_col}, {northing_col}), '{_CRS_OSGB}', '{_CRS_WGS84}')"
        )
    rel = con.sql(
        f"SELECT * EXCLUDE ({easting_col}, {northing_col}), {geom_expr} AS geom FROM stats19_spatial"
    )

    if return_type == "relation":
        return rel
    df = rel.df()
    # duckdb spatial returns geometry as WKB bytearray already
    df["geom"] = df["geom"].map(lambda g: bytes(g) if g is not None else None)
    if return_type == "wkb":
        return df
    # "dataframe": keep WKB bytes in a plain column (no geopandas dependency)
    return df


def st_transform_geometry(
    rel: duckdb.DuckDBPyRelation,
    to_crs: str = _CRS_WGS84,
    from_crs: str = _CRS_OSGB,
) -> duckdb.DuckDBPyRelation:
    """Transform a DuckDB spatial relation's geometry column to another CRS.

    Args:
        rel: relation with a ``geom`` column (from :func:`format_sf`).
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    df = rel.df()
    df["geom"] = df["geom"].map(lambda g: bytes(g) if g is not None else None)
    con.register("transform_src", df)
    return con.sql(
        "SELECT * EXCLUDE (geom), "
        "ST_Transform(ST_GeomFromWKB(geom), "
        f"'{from_crs}', '{to_crs}') AS geom FROM transform_src"
    )


def read_geoparquet(path: str) -> duckdb.DuckDBPyRelation:
    """Read a GeoParquet file into a DuckDB relation (spatial column preserved)."""
    con = duckdb.connect()
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    return con.sql(f"SELECT * FROM '{path}'")


def write_geoparquet(df: pd.DataFrame, path: str) -> str:
    """Write a DataFrame with a WKB ``geom`` column to GeoParquet."""
    con = duckdb.connect()
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    con.register("g", df)
    con.execute(f"COPY (SELECT * FROM g) TO '{path}' (FORMAT 'parquet')")
    return path
