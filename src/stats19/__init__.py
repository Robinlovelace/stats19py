"""stats19: work with UK STATS19 road casualty data.

Python port of the R package of the same name (ropensci/stats19).
Download, read and format road traffic casualty data from Great Britain,
published by the Department for Transport.
"""

from __future__ import annotations

from stats19.files import (
    file_names,
    find_file_name,
    get_data_directory,
    get_url,
    list_files,
    locate_files,
    locate_one_file,
    set_data_directory,
)

__version__ = "0.1.0"

__all__ = [
    "file_names",
    "find_file_name",
    "get_data_directory",
    "get_url",
    "list_files",
    "locate_files",
    "locate_one_file",
    "set_data_directory",
]


def main() -> None:
    """CLI entry point (placeholder)."""
    print(f"stats19 v{__version__}: Python port of the R stats19 package")
