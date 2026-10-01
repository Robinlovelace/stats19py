"""Use pre-downloaded STATS19 files and never fetch what is already on disk.

DfT has renamed its files over time. ``accident`` became ``collision``, and
the cumulative history file has appeared both as ``1979-2021`` and as
``1979-latest-published-year``. The embedded manifest (``file_names.txt``,
from the R package) only knows the current names, so a data directory filled
over several years contains files the manifest cannot see.

This module scans a data directory, recognises every naming vintage, and
decides which local files can answer a request. Only when nothing local
covers the request does it name the manifest files that would have to be
downloaded.

Large cumulative files are filtered by year with DuckDB, which streams the
CSV, so a single year is read without loading the full 1979 history into
memory.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from stats19 import data

#: Set to 1, true or yes to forbid all downloads.
OFFLINE_ENV = "STATS19_OFFLINE"

_PREFIX = "dft-road-casualty-statistics-"
_NAME_RE = re.compile(
    r"^dft-road-casualty-statistics-(?P<table>accident|collision|casualty|vehicle)-"
    r"(?P<span>\d{4}|1979-latest-published-year|1979-\d{4}|last-5-years)\.csv$"
)


class OfflineError(FileNotFoundError):
    """Raised when a request needs a download but downloads are forbidden."""


def is_offline(offline: bool | None = None) -> bool:
    """True if downloads are forbidden, by argument or by ``STATS19_OFFLINE``."""
    if offline is not None:
        return offline
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class LocalFile:
    """One STATS19 table file found on disk."""

    path: str
    name: str
    table: str  # collision, casualty or vehicle (accident is mapped to collision)
    span: str  # "2019", "1979-latest-published-year", "1979-2021" or "last-5-years"
    in_manifest: bool

    @property
    def kind(self) -> str:
        if self.span.isdigit():
            return "year"
        if self.span == "last-5-years":
            return "last5"
        return "cumulative"

    def covers(self, year: int) -> bool:
        """Whether the file name promises rows for ``year``.

        ``1979-latest-published-year`` has no end year in its name, so it is
        taken to cover every year from 1979. ``last-5-years`` files never
        cover a specific year, because their range depends on when they were
        downloaded.
        """
        if self.kind == "year":
            return int(self.span) == year
        if self.span == "1979-latest-published-year":
            return year >= 1979
        if self.kind == "cumulative":
            return 1979 <= year <= int(self.span.split("-")[1])
        return False


def inventory(data_dir: str) -> list[LocalFile]:
    """Every recognised STATS19 table file in ``data_dir``, sorted by name."""
    if not os.path.isdir(data_dir):
        return []
    manifest = set(data.file_names())
    found = []
    for name in sorted(os.listdir(data_dir)):
        m = _NAME_RE.match(name)
        if not m:
            continue
        table = "collision" if m["table"] == "accident" else m["table"]
        found.append(
            LocalFile(
                path=os.path.join(data_dir, name),
                name=name,
                table=table,
                span=m["span"],
                in_manifest=name in manifest,
            )
        )
    return found


def manifest_mismatches(data_dir: str) -> dict[str, list[str]]:
    """Compare a data directory with the embedded manifest.

    Returns ``not_in_manifest`` (STATS19 files on disk under a name the
    manifest does not list) and ``manifest_not_on_disk`` (manifest names
    absent from disk).
    """
    on_disk = {f.name for f in inventory(data_dir)}
    manifest = set(data.file_names())
    return {
        "not_in_manifest": sorted(on_disk - manifest),
        "manifest_not_on_disk": sorted(manifest - on_disk),
    }


@dataclass
class Resolution:
    """Which local files answer a request, and what is still missing.

    ``year_filter`` is the list of years to keep when ``files`` includes a
    multi-year file, or ``None`` to keep everything.
    """

    table: str
    files: list[LocalFile] = field(default_factory=list)
    year_filter: list[int] | None = None
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _int_years(years: int | list[int] | str | None) -> list[int] | None:
    """Specific calendar years, or ``None`` for whole-history and last-5 requests."""
    if years is None or isinstance(years, str):
        return None
    years_list = [years] if isinstance(years, int) else list(years)
    ints = [y for y in years_list if isinstance(y, int) and y >= 1979]
    return ints if ints and len(ints) == len(years_list) else None


def resolve(
    table: str,
    years: int | list[int] | str | None,
    data_dir: str,
) -> Resolution:
    """Decide which local files answer ``table`` for ``years``.

    Order of preference:

    1. The manifest files R would use, if all are on disk. This keeps R
       behaviour unchanged when the directory matches the manifest.
    2. A local ``1979-latest-published-year`` file, filtered by year. One
       file means one data vintage for every requested year.
    3. Per-year files under any naming vintage, with ``1979-YYYY`` files
       filling gaps. These may be older vintages, so a note is added.

    Anything not covered is listed in ``missing`` as manifest names.
    """
    from stats19.core import find_file_name

    res = Resolution(table=table)
    wanted = find_file_name(years=years, type=table)
    local = [f for f in inventory(data_dir) if f.table == table]
    by_name = {f.name: f for f in local}
    int_years = _int_years(years)

    if wanted and all(w in by_name for w in wanted):
        res.files = [by_name[w] for w in wanted]
        if any(f.kind == "cumulative" for f in res.files) and int_years is not None:
            res.year_filter = sorted(set(int_years))
        return res

    if int_years is None:
        # Whole history or last 5 years: only the exact manifest files will do.
        res.missing = [w for w in wanted if w not in by_name]
        return res

    res.year_filter = sorted(set(int_years))
    latest = [f for f in local if f.span == "1979-latest-published-year"]
    if latest:
        res.files = latest[:1]
        return res

    chosen: list[LocalFile] = []
    uncovered: list[int] = []
    for y in res.year_filter:
        per_year = [f for f in local if f.kind == "year" and f.covers(y)]
        history = [f for f in local if f.kind == "cumulative" and f.covers(y)]
        pick = (per_year or history or [None])[0]
        if pick is None:
            uncovered.append(y)
        elif pick not in chosen:
            chosen.append(pick)
    if uncovered:
        res.missing = [w for w in wanted if w not in by_name]
        res.notes.append(f"No local {table} file covers {uncovered}")
        return res
    res.files = chosen
    legacy = [f.name for f in chosen if not f.in_manifest]
    if legacy:
        res.notes.append(
            "Using files outside the manifest, which may be an older DfT vintage: "
            + ", ".join(legacy)
        )
    return res


def _year_column(con, path: str) -> str | None:  # noqa: ANN001
    cols = con.execute(
        "SELECT * FROM read_csv(?, all_varchar = true, header = true) LIMIT 0", [path]
    ).description
    names = [c[0].lstrip("﻿") for c in cols]
    return next((c for c in names if c in ("collision_year", "accident_year")), None)


@contextmanager
def year_slice(path: str, years: list[int]) -> Iterator[str]:
    """Yield a temporary CSV holding only ``years`` from ``path``.

    DuckDB reads every column as text and writes it back unchanged, so the
    slice parses exactly like the original file. The temporary file is
    removed on exit.
    """
    import duckdb

    con = duckdb.connect()
    try:
        year_col = _year_column(con, path)
        if year_col is None:
            yield path
            return
        fd, tmp = tempfile.mkstemp(prefix="stats19-", suffix=".csv")
        os.close(fd)
        try:
            in_list = ", ".join(str(int(y)) for y in years)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM read_csv(?, all_varchar = true, header = true)
                    WHERE TRY_CAST("{year_col}" AS INTEGER) IN ({in_list})
                ) TO '{tmp}' (HEADER, DELIMITER ',')
                """,
                [path],
            )
            yield tmp
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    finally:
        con.close()
