"""Download STATS19 data files from the DfT.

Port of the R package's ``dl_stats19()`` (v4.1.0-dev semantics).
"""

from __future__ import annotations

import os
import urllib.request

from stats19.files import find_file_name, get_data_directory, get_url


def dl_stats19(
    year: int | list[int] | str | None = None,
    type: str | None = None,
    data_dir: str | None = None,
    file_name: str | None = None,
    silent: bool = False,
    timeout: int = 600,
) -> str | None:
    """Download STATS19 data for a given year (and optionally type).

    Mirrors R ``dl_stats19()``: filenames are inferred from ``year``/``type``
    unless ``file_name`` is given; files that already exist in ``data_dir``
    are skipped. Returns the path of the (last) downloaded file, or ``None``
    if nothing was downloaded.

    Parameters
    ----------
    year:
        Single year, list of years, ``"all"``, or ``None`` for all files.
    type:
        One of ``"collision"``, ``"casualty"``, ``"vehicle"`` or ``"all"``
        (case-insensitive); ``None``/``"all"`` means all types.
    data_dir:
        Directory to save files to. Defaults to ``get_data_directory()``.
    file_name:
        Optional specific filename to download instead of inferring.
    silent:
        Suppress progress messages.
    timeout:
        Download timeout in seconds (default 600, like R).
    """
    data_dir = data_dir or get_data_directory()
    if file_name is not None:
        fnames = [file_name]
    else:
        type_arg = None if type is None or type.lower() == "all" else type
        fnames = find_file_name(years=year, type=type_arg)

    if not fnames:
        if not silent:
            print("No files found. Check the stats19 website on data.gov.uk")
        return None

    if not silent:
        print("Files identified: " + ", ".join(fnames))

    os.makedirs(data_dir, exist_ok=True)
    last_path: str | None = None
    for f in fnames:
        destfile = os.path.join(data_dir, f)
        if os.path.exists(destfile):
            if not silent:
                print(f"Data already exists in data_dir, not downloading: {f}")
            last_path = destfile
            continue

        file_url = get_url(f)
        try:
            with (
                urllib.request.urlopen(file_url, timeout=timeout) as resp,
                open(  # noqa: S310
                    destfile, "wb"
                ) as out,
            ):
                out.write(resp.read())
            if not silent:
                print(f"Data saved at {destfile}")
            last_path = destfile
        except Exception:
            print(f"Failed to download file: {file_url}")
            if os.path.exists(destfile):
                os.remove(destfile)
    return last_path


def ensure_downloaded(
    year: int | list[int] | str | None = None,
    type: str | None = None,
    data_dir: str | None = None,
    silent: bool = True,
    timeout: int = 600,
) -> list[str]:
    """Download any missing files and return the paths of all requested files.

    Convenience wrapper used by the read functions: downloads what is missing,
    then returns the on-disk paths (like R's ``locate_files()`` after download).
    """
    data_dir = data_dir or get_data_directory()
    type_arg = None if type is None or type.lower() == "all" else type
    fnames = find_file_name(years=year, type=type_arg)
    dl_stats19(year=year, type=type, data_dir=data_dir, silent=silent, timeout=timeout)
    paths = [os.path.join(data_dir, f) for f in fnames]
    return [p for p in paths if os.path.exists(p)]
