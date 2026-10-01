"""stats19: work with UK STATS19 road casualty data.

Python port of the R package of the same name (ropensci/stats19 v4.1.0-dev),
deliberately smaller and more schema-driven. Download, read and format road
traffic casualty data from Great Britain, published by the Department for
Transport.

Public API (mirrors the R package where sensible):

    dl_stats19(year, type)         # download CSVs
    read_collisions(year)          # read + format collisions
    read_casualties(year)          # read + format casualties
    read_vehicles(year)            # read + format vehicles
    get_stats19(year, type)        # download + read + format
    list_files(year, table)        # discover available files
    format_* / format_column_names # format DataFrames
    get_url / locate_files         # URLs and on-disk paths
"""

from __future__ import annotations

from stats19.api import get_MOT, get_stats19_adjustments, get_ULEZ
from stats19.clean import (
    clean_make,
    clean_make_model,
    clean_model,
    extract_make_stats19,
)
from stats19.core import (
    dl_stats19,
    find_file_name,
    format_casualties,
    format_collisions,
    format_column_names,
    format_stats19,
    format_vehicles,
    get_casualties,
    get_collisions,
    get_data_directory,
    get_stats19,
    get_url,
    get_vehicles,
    list_files,
    locate_files,
    locate_one_file,
    read_casualties,
    read_collisions,
    read_stats19,
    read_vehicles,
    set_data_directory,
)
from stats19.layer import casualty_layer
from stats19.local import OfflineError, manifest_mismatches
from stats19.spatial import (
    format_sf,
    read_geoparquet,
    st_transform_geometry,
    write_geoparquet,
)

__version__ = "0.1.0"

__all__ = [
    "OfflineError",
    "casualty_layer",
    "manifest_mismatches",
    "clean_make",
    "clean_make_model",
    "clean_model",
    "dl_stats19",
    "extract_make_stats19",
    "find_file_name",
    "format_casualties",
    "format_collisions",
    "format_column_names",
    "format_sf",
    "format_stats19",
    "format_vehicles",
    "get_MOT",
    "get_ULEZ",
    "get_casualties",
    "get_collisions",
    "get_data_directory",
    "get_stats19",
    "get_stats19_adjustments",
    "get_url",
    "get_vehicles",
    "list_files",
    "locate_files",
    "locate_one_file",
    "read_casualties",
    "read_collisions",
    "read_geoparquet",
    "read_stats19",
    "read_vehicles",
    "set_data_directory",
    "st_transform_geometry",
    "write_geoparquet",
]


def _parse_years(text: str) -> list[int]:
    years: list[int] = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        years.extend(range(int(a), int(b or a) + 1))
    return years


def main(argv: list[str] | None = None) -> None:
    """Command line interface. Run ``stats19 --help``."""
    import argparse

    ap = argparse.ArgumentParser(prog="stats19", description=f"stats19 v{__version__}")
    sub = ap.add_subparsers(dest="command")
    cl = sub.add_parser(
        "casualties",
        help="Write collisions and casualties for an area to Parquet, from local files only",
    )
    cl.add_argument("--years", required=True, help="e.g. 2024 or 2019-2024 or 2015,2019-2021")
    cl.add_argument("--out", required=True, help="output directory")
    cl.add_argument("--authority", action="append", help="ONS code, repeatable")
    cl.add_argument("--bbox", help="xmin,ymin,xmax,ymax")
    cl.add_argument("--bbox-crs", default="EPSG:4326", choices=["EPSG:4326", "EPSG:27700"])
    cl.add_argument("--data-dir", help="default: STATS19_DOWNLOAD_DIRECTORY, then ./data")
    chk = sub.add_parser("check", help="Compare a data directory with the embedded manifest")
    chk.add_argument("--data-dir", help="default: STATS19_DOWNLOAD_DIRECTORY, then ./data")
    args = ap.parse_args(argv)

    if args.command == "casualties":
        summary = casualty_layer(
            _parse_years(args.years),
            args.out,
            authorities=args.authority,
            bbox=[float(v) for v in args.bbox.split(",")] if args.bbox else None,
            bbox_crs=args.bbox_crs,
            data_dir=args.data_dir,
        )
        for row in summary["rows_by_year"]:
            print(
                f"{row['year']}: {row['collisions']} collisions, "
                f"{row['casualties']} casualties, {row['ksi']} KSI"
            )
        for note in summary["notes"]:
            print(note)
        if summary["years_with_no_rows"]:
            print(f"No rows for years: {summary['years_with_no_rows']}")
        print(f"Wrote {args.out}")
    elif args.command == "check":
        mm = manifest_mismatches(args.data_dir or get_data_directory())
        for key, names in mm.items():
            print(f"{key} ({len(names)}):")
            for n in names:
                print(f"  {n}")
    else:
        ap.print_help()
