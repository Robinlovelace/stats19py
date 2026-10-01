"""Casualty layer: collisions and casualties for an area and years, as Parquet.

This is the ingest step for downstream risk analysis. It reads only files
already on disk (see :mod:`stats19.local`) and never downloads. All work is
done in DuckDB, which streams the CSVs, so a few years for one authority can
be cut from the 1979 history files without loading them into memory.

Two tables are written:

``collisions.parquet``
    One row per collision: location (WGS84 and British National Grid, as
    published), date, authority codes, road context, severity, casualty
    counts by severity and by mode, and adjusted KSI.
``casualties.parquet``
    One row per casualty: severity, adjusted severity probabilities, mode,
    class, age and sex, with the collision's year, location and authority
    codes repeated so the table can be aggregated on its own.

A ``casualty_layer.json`` file records the inputs, filters and row counts.

Adjusted severity
    Police forces moved to injury-based reporting (CRASH) in different
    years, which raised the share of casualties recorded as serious. DfT
    publishes, per casualty, the probability that it would have been
    serious under the injury-based system. ``ksi_adjusted`` (fatal plus
    that probability) is comparable across forces and years and is what a
    trend or cross-authority risk metric should use. It is published from
    2004.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime

from stats19 import local

#: Mode of travel from ``casualty_type`` codes, including 1979 to 2004 codes.
#: E-scooter riders are also taken from ``escooter_flag`` where the file has it.
#: Code 33 is in neither the R schema nor the 2025 DfT data guide, but in the
#: 1979-latest casualty file 6015 of its 6103 rows (2020 to 2025) have
#: ``escooter_flag`` 1, "Casualty was using an e-scooter".
MODES: dict[str, tuple[int, ...]] = {
    "pedestrian": (0,),
    "cyclist": (1,),
    "e_scooter": (33,),
    "motorcycle": (2, 3, 4, 5, 23, 97, 103, 104, 105, 106),
    "car": (8, 9, 108, 109),
    "bus": (10, 11, 110),
    "goods": (19, 20, 21, 98, 113),
}
MODE_ORDER = ("pedestrian", "cyclist", "e_scooter", "motorcycle", "car", "bus", "goods", "other")

#: Authority fields matched by default. ``local_authority_highway_current``
#: is recoded by DfT to current boundaries, so a multi-year window stays
#: consistent across reorganisations. ``local_authority_ons_district`` is
#: coded as at the collision date and lets two-tier district codes match.
AUTHORITY_FIELDS = ("local_authority_highway_current", "local_authority_ons_district")

# Target column -> names it has had in earlier DfT vintages.
_ALIASES = {
    "collision_index": ("collision_index", "accident_index"),
    "collision_year": ("collision_year", "accident_year"),
    "collision_severity": ("collision_severity", "accident_severity"),
}

_COLLISION_COLS = (
    "collision_index",
    "collision_year",
    "date",
    "time",
    "longitude",
    "latitude",
    "location_easting_osgr",
    "location_northing_osgr",
    "police_force",
    "local_authority_ons_district",
    "local_authority_highway",
    "local_authority_highway_current",
    "collision_severity",
    "number_of_vehicles",
    "number_of_casualties",
    "first_road_class",
    "road_type",
    "speed_limit",
    "urban_or_rural_area",
    "light_conditions",
    "trunk_road_flag",
    "lsoa_of_accident_location",
)
_CASUALTY_COLS = (
    "collision_index",
    "vehicle_reference",
    "casualty_reference",
    "casualty_class",
    "casualty_severity",
    "casualty_type",
    "sex_of_casualty",
    "age_of_casualty",
    "age_band_of_casualty",
    "casualty_adjusted_severity_serious",
    "casualty_adjusted_severity_slight",
    "escooter_flag",
)


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _source_sql(con, files: list[local.LocalFile], wanted: Sequence[str]) -> str:  # noqa: ANN001
    """One SELECT per file with columns renamed to current names, unioned."""
    parts = []
    for f in files:
        cols = {
            c[0].lstrip("﻿")
            for c in con.execute(
                "SELECT * FROM read_csv(?, all_varchar = true, header = true) LIMIT 0", [f.path]
            ).description
        }
        select = []
        for target in wanted:
            source = next((a for a in _ALIASES.get(target, (target,)) if a in cols), None)
            expr = f"NULLIF(NULLIF({_q(source)}, '-1'), '')" if source else "NULL"
            select.append(f"{expr} AS {_q(target)}")
        parts.append(
            f"SELECT {', '.join(select)} FROM read_csv({_lit(f.path)}, "
            "all_varchar = true, header = true)"
        )
    return " UNION ALL ".join(parts)


def _resolve(table: str, years: list[int], data_dir: str) -> local.Resolution:
    res = local.resolve(table, years, data_dir)
    if res.missing or not res.files:
        raise local.OfflineError(
            f"No local {table} data for {years} in {data_dir}. The casualty layer never "
            f"downloads. Missing: {', '.join(res.missing) or 'all files'}"
        )
    return res


def _years(years: int | Sequence[int]) -> list[int]:
    out = sorted({int(y) for y in ([years] if isinstance(years, int) else years)})
    if not out or out[0] < 1979:
        raise ValueError(f"years must be calendar years from 1979, got {years!r}")
    return out


def casualty_layer(
    years: int | Sequence[int],
    out_dir: str,
    *,
    authorities: Sequence[str] | None = None,
    authority_fields: Sequence[str] = AUTHORITY_FIELDS,
    bbox: Sequence[float] | None = None,
    bbox_crs: str = "EPSG:4326",
    data_dir: str | None = None,
) -> dict:
    """Write collisions and casualties for an area and years to ``out_dir``.

    Parameters
    ----------
    years
        Calendar years, for example ``range(2019, 2025)``.
    out_dir
        Directory for ``collisions.parquet``, ``casualties.parquet`` and
        ``casualty_layer.json``. Created if absent.
    authorities
        ONS codes. A collision is kept if any of ``authority_fields`` holds
        one of them. Pass highway authority codes (E06, E08, E09, E10) for
        a consistent multi-year window, or district codes (E07) to match
        districts as they were at the time.
    bbox
        ``(xmin, ymin, xmax, ymax)`` in ``bbox_crs``, which is ``EPSG:4326``
        (longitude, latitude) or ``EPSG:27700`` (easting, northing).
        Collisions without coordinates are dropped when a bbox is given.
    data_dir
        Directory of pre-downloaded DfT CSVs. Defaults to
        ``STATS19_DOWNLOAD_DIRECTORY``, then ``./data``.

    Returns the summary that is also written to ``casualty_layer.json``.
    Raises :class:`stats19.local.OfflineError` if local files do not cover
    the request.
    """
    import duckdb

    from stats19 import __version__
    from stats19.core import get_data_directory

    data_dir = data_dir or get_data_directory()
    year_list = _years(years)
    if bbox is not None and len(bbox) != 4:
        raise ValueError("bbox must be (xmin, ymin, xmax, ymax)")
    if bbox_crs not in ("EPSG:4326", "EPSG:27700"):
        raise ValueError("bbox_crs must be EPSG:4326 or EPSG:27700")
    bad_fields = set(authority_fields) - set(_COLLISION_COLS)
    if bad_fields:
        raise ValueError(f"unknown authority fields: {sorted(bad_fields)}")

    col_res = _resolve("collision", year_list, data_dir)
    cas_res = _resolve("casualty", year_list, data_dir)
    os.makedirs(out_dir, exist_ok=True)

    con = duckdb.connect()
    con.execute(f"CREATE TEMP VIEW col_src AS {_source_sql(con, col_res.files, _COLLISION_COLS)}")
    con.execute(f"CREATE TEMP VIEW cas_src AS {_source_sql(con, cas_res.files, _CASUALTY_COLS)}")

    where = [f"TRY_CAST(collision_year AS INTEGER) IN ({', '.join(map(str, year_list))})"]
    if authorities:
        codes = ", ".join(_lit(c) for c in authorities)
        where.append("(" + " OR ".join(f"{_q(f)} IN ({codes})" for f in authority_fields) + ")")
    if bbox is not None:
        x, y = (
            ("longitude", "latitude")
            if bbox_crs == "EPSG:4326"
            else ("location_easting_osgr", "location_northing_osgr")
        )
        xmin, ymin, xmax, ymax = (float(v) for v in bbox)
        where.append(
            f"TRY_CAST({x} AS DOUBLE) BETWEEN {xmin} AND {xmax} "
            f"AND TRY_CAST({y} AS DOUBLE) BETWEEN {ymin} AND {ymax}"
        )

    mode_case = " ".join(
        f"WHEN t IN ({', '.join(map(str, codes))}) THEN '{mode}'" for mode, codes in MODES.items()
    )
    con.execute(f"""
        CREATE TEMP TABLE col AS
        SELECT
            collision_index,
            CAST(collision_year AS INTEGER) AS collision_year,
            TRY_STRPTIME(date, '%d/%m/%Y')::DATE AS date,
            time,
            TRY_CAST(longitude AS DOUBLE) AS longitude,
            TRY_CAST(latitude AS DOUBLE) AS latitude,
            TRY_CAST(location_easting_osgr AS DOUBLE) AS easting,
            TRY_CAST(location_northing_osgr AS DOUBLE) AS northing,
            police_force,
            local_authority_ons_district,
            local_authority_highway,
            local_authority_highway_current,
            TRY_CAST(collision_severity AS INTEGER) AS collision_severity,
            TRY_CAST(number_of_vehicles AS INTEGER) AS number_of_vehicles,
            TRY_CAST(number_of_casualties AS INTEGER) AS number_of_casualties,
            TRY_CAST(first_road_class AS INTEGER) AS first_road_class,
            TRY_CAST(road_type AS INTEGER) AS road_type,
            TRY_CAST(speed_limit AS INTEGER) AS speed_limit,
            TRY_CAST(urban_or_rural_area AS INTEGER) AS urban_or_rural_area,
            TRY_CAST(light_conditions AS INTEGER) AS light_conditions,
            TRY_CAST(trunk_road_flag AS INTEGER) AS trunk_road_flag,
            lsoa_of_accident_location AS lsoa
        FROM col_src
        WHERE {" AND ".join(where)}
    """)
    con.execute(f"""
        CREATE TEMP TABLE cas AS
        WITH c AS (
            SELECT s.*, TRY_CAST(s.casualty_type AS INTEGER) AS t
            FROM cas_src s SEMI JOIN col USING (collision_index)
        )
        SELECT
            c.collision_index,
            col.collision_year,
            TRY_CAST(c.vehicle_reference AS INTEGER) AS vehicle_reference,
            TRY_CAST(c.casualty_reference AS INTEGER) AS casualty_reference,
            TRY_CAST(c.casualty_severity AS INTEGER) AS casualty_severity,
            CASE TRY_CAST(c.casualty_severity AS INTEGER)
                WHEN 1 THEN 'fatal' WHEN 2 THEN 'serious' WHEN 3 THEN 'slight' END AS severity,
            TRY_CAST(c.casualty_adjusted_severity_serious AS DOUBLE) AS adjusted_serious,
            TRY_CAST(c.casualty_adjusted_severity_slight AS DOUBLE) AS adjusted_slight,
            c.t AS casualty_type,
            CASE WHEN c.escooter_flag = '1' THEN 'e_scooter' {mode_case} ELSE 'other' END AS mode,
            TRY_CAST(c.casualty_class AS INTEGER) AS casualty_class,
            TRY_CAST(c.sex_of_casualty AS INTEGER) AS sex_of_casualty,
            TRY_CAST(c.age_of_casualty AS INTEGER) AS age_of_casualty,
            TRY_CAST(c.age_band_of_casualty AS INTEGER) AS age_band_of_casualty,
            col.date, col.longitude, col.latitude, col.easting, col.northing,
            col.local_authority_ons_district, col.local_authority_highway,
            col.local_authority_highway_current
        FROM c JOIN col USING (collision_index)
    """)

    mode_counts = ",\n".join(f"count(*) FILTER (WHERE mode = '{m}') AS n_{m}" for m in MODE_ORDER)
    con.execute(f"""
        CREATE TEMP TABLE out_col AS
        SELECT
            col.*,
            CASE col.collision_severity
                WHEN 1 THEN 'fatal' WHEN 2 THEN 'serious' WHEN 3 THEN 'slight' END AS severity,
            coalesce(k.n_casualties, 0) AS n_casualties,
            coalesce(k.n_fatal, 0) AS n_fatal,
            coalesce(k.n_serious, 0) AS n_serious,
            coalesce(k.n_slight, 0) AS n_slight,
            coalesce(k.n_fatal, 0) + coalesce(k.n_serious, 0) AS n_ksi,
            k.ksi_adjusted,
            {", ".join(f"coalesce(k.n_{m}, 0) AS n_{m}" for m in MODE_ORDER)}
        FROM col LEFT JOIN (
            SELECT
                collision_index,
                count(*) AS n_casualties,
                count(*) FILTER (WHERE casualty_severity = 1) AS n_fatal,
                count(*) FILTER (WHERE casualty_severity = 2) AS n_serious,
                count(*) FILTER (WHERE casualty_severity = 3) AS n_slight,
                -- NULL when any casualty in the collision lacks an adjusted value.
                CASE WHEN count(adjusted_serious) = count(*) THEN
                    sum(CASE WHEN casualty_severity = 1 THEN 1.0 ELSE adjusted_serious END)
                END AS ksi_adjusted,
                {mode_counts}
            FROM cas GROUP BY collision_index
        ) k USING (collision_index)
        ORDER BY collision_year, collision_index
    """)

    col_path = os.path.join(out_dir, "collisions.parquet")
    cas_path = os.path.join(out_dir, "casualties.parquet")
    con.execute(f"COPY out_col TO {_lit(col_path)} (FORMAT parquet, COMPRESSION zstd)")
    con.execute(
        f"COPY (SELECT * FROM cas ORDER BY collision_year, collision_index, casualty_reference) "
        f"TO {_lit(cas_path)} (FORMAT parquet, COMPRESSION zstd)"
    )

    per_year = con.execute("""
        SELECT collision_year, count(*), sum(n_casualties), sum(n_ksi),
               count(*) FILTER (WHERE longitude IS NULL)
        FROM out_col GROUP BY 1 ORDER BY 1
    """).fetchall()
    orphans = con.execute("SELECT count(*) FROM out_col WHERE n_casualties = 0").fetchone()
    con.close()

    found_years = {r[0] for r in per_year}
    summary = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "stats19_version": __version__,
        "data_dir": data_dir,
        "inputs": {
            "collision": [f.name for f in col_res.files],
            "casualty": [f.name for f in cas_res.files],
        },
        "notes": col_res.notes + cas_res.notes,
        "filters": {
            "years": year_list,
            "authorities": list(authorities) if authorities else None,
            "authority_fields": list(authority_fields) if authorities else None,
            "bbox": list(bbox) if bbox is not None else None,
            "bbox_crs": bbox_crs if bbox is not None else None,
        },
        "outputs": {"collisions": col_path, "casualties": cas_path},
        "rows_by_year": [
            {
                "year": y,
                "collisions": n,
                "casualties": int(c or 0),
                "ksi": int(k or 0),
                "collisions_without_coordinates": nc,
            }
            for y, n, c, k, nc in per_year
        ],
        "collisions_without_casualty_rows": orphans[0] if orphans else 0,
        "years_with_no_rows": [y for y in year_list if y not in found_years],
    }
    with open(os.path.join(out_dir, "casualty_layer.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
        fh.write("\n")
    return summary
