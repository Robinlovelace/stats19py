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

from stats19.core import (
    dl_stats19,
    find_file_name,
    format_casualties,
    format_collisions,
    format_column_names,
    format_stats19,
    format_vehicles,
    get_data_directory,
    get_stats19,
    get_url,
    list_files,
    locate_files,
    locate_one_file,
    read_casualties,
    read_collisions,
    read_stats19,
    read_vehicles,
    set_data_directory,
)

__version__ = "0.1.0"

__all__ = [
    "dl_stats19",
    "find_file_name",
    "format_casualties",
    "format_collisions",
    "format_column_names",
    "format_stats19",
    "format_vehicles",
    "get_data_directory",
    "get_stats19",
    "get_url",
    "list_files",
    "locate_files",
    "locate_one_file",
    "read_casualties",
    "read_collisions",
    "read_stats19",
    "read_vehicles",
    "set_data_directory",
]


def main() -> None:
    """CLI entry point (placeholder)."""
    print(f"stats19 v{__version__}: Python port of the R stats19 package")
