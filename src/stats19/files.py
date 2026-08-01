"""File discovery and URL construction for STATS19 data.

Port of the R package's ``find_file_name()``, ``get_url()``,
``get_data_directory()`` and ``set_data_directory()`` (v4.1.0-dev).
"""

from __future__ import annotations

import importlib.resources as resources
import os

_DATA_DIR_ENV = "STATS19_DOWNLOAD_DIRECTORY"
_DEFAULT_DIRECTORY = "road-accidents-safety-data"
_DOMAIN = "https://data.dft.gov.uk"

_CACHED_FILE_NAMES: list[str] | None = None


def _load_file_names() -> list[str]:
    """Load the embedded list of DfT STATS19 filenames (26 files)."""
    global _CACHED_FILE_NAMES
    if _CACHED_FILE_NAMES is None:
        text = (
            resources.files("stats19")
            .joinpath("data", "file_names.txt")
            .read_text(encoding="utf-8")
        )
        _CACHED_FILE_NAMES = [line.strip() for line in text.splitlines() if line.strip()]
    return list(_CACHED_FILE_NAMES)


def file_names() -> list[str]:
    """Return the full manifest of known STATS19 data filenames."""
    return _load_file_names()


def list_files(year: int | None = None, table: str | None = None) -> list[str]:
    """List available STATS19 files, optionally filtered by year and table.

    Python-idiomatic wrapper (py-stats19 convention) around ``find_file_name``.
    """
    return find_file_name(years=year, type=table)


def get_data_directory() -> str:
    """Return the directory where STATS19 data are stored.

    Mirrors the R package: the ``STATS19_DOWNLOAD_DIRECTORY`` environment
    variable takes precedence, otherwise a ``data`` directory under the
    current working directory is used.
    """
    env_dir = os.environ.get(_DATA_DIR_ENV)
    if env_dir:
        return env_dir
    return os.path.join(os.getcwd(), "data")


def set_data_directory(path: str) -> None:
    """Set the STATS19 download directory (persisted via env var in-process)."""
    os.environ[_DATA_DIR_ENV] = path


def find_file_name(
    years: int | list[int] | str | None = None, type: str | None = None
) -> list[str]:
    """Find STATS19 filenames for the requested years and data type.

    Port of R ``find_file_name()`` with v4.1.0-dev semantics:

    - ``years=None``: all known files
    - ``years="all"``: the cumulative ``1979-latest`` files only
    - any year < 2021: resolved to the cumulative ``1979-latest`` files
    - years >= 2021: individual per-year files (plus ``last-5-years`` if the
      special value ``5``/``"5 years"`` is requested alongside)
    - ``type`` filters by collisions/casualty/vehicles (case-insensitive)
    """
    all_files = _load_file_names()

    if years is None:
        result = all_files
    elif years == "all":
        result = [f for f in all_files if "1979-latest" in f]
    else:
        years_list = [years] if isinstance(years, int) else list(years)
        result: list[str] = []
        if any(y < 2021 for y in years_list if isinstance(y, int)):
            # 1979-latest already contains all years
            result = [f for f in all_files if "1979-latest" in f]
        else:
            indiv = [y for y in years_list if isinstance(y, int) and 2021 <= y <= 2050]
            for y in indiv:
                result.extend(
                    f for f in all_files if str(y) in f and "1979" not in f and "adjust" not in f
                )
            if any(y == 5 or y == "5 years" for y in years_list):
                result.extend(f for f in all_files if "last-5-years" in f and "adjust" not in f)

    if type is not None:
        # R does gsub("cas", "ics-cas", type): "casualty" -> "ics-casualty"
        type_pattern = type.lower().replace("cas", "ics-cas")
        result = [f for f in result if type_pattern in f]

    # De-duplicate while preserving order (R returns unique())
    seen: set[str] = set()
    unique_result = [f for f in result if not (f in seen or seen.add(f))]
    return unique_result


def get_url(file_name: str = "", domain: str = _DOMAIN, directory: str = _DEFAULT_DIRECTORY) -> str:
    """Convert a filename to a full download URL (R ``get_url()``)."""
    return f"{domain}/{directory}/{file_name}"


def locate_files(
    data_dir: str | None = None, type: str | None = None, years: int | list[int] | str | None = None
) -> list[str]:
    """Return paths of requested files that exist on disk (R ``locate_files()``)."""
    data_dir = data_dir or get_data_directory()
    paths = [os.path.join(data_dir, f) for f in find_file_name(years=years, type=type)]
    return [p for p in paths if os.path.exists(p)]


def locate_one_file(
    filename: str | None = None,
    data_dir: str | None = None,
    year: int | None = None,
    type: str | None = None,
) -> str:
    """Return a single file path on disk (R ``locate_one_file()``)."""
    data_dir = data_dir or get_data_directory()
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"No files found under: {data_dir}")
    paths = locate_files(data_dir=data_dir, type=type, years=year)
    if not paths:
        raise FileNotFoundError(f"No files found under: {data_dir}")
    if filename is not None:
        paths = [p for p in paths if filename in os.path.basename(p)]
    return paths[0]
