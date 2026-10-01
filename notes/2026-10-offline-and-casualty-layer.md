# Offline data and casualty layer: measurements (2026-10-01)

All runs on branch `fix/embedded-data-offline`. "Offline" means
`unshare -rn`, which removes all network interfaces from the process.
`LAKE=/mnt/secondary/data/stats19` (a symlink to
`/mnt/secondary/data/bronze/dft/stats19`, the same inode, no duplication).

## Fresh clone

| state | command | result |
|-------|---------|--------|
| `e71a229` | `uv sync --extra dev && uv run pytest` | 12 failed, 25 passed, 24 skipped |
| `e71a229` | `uv sync && uv run pytest` | pytest not installed (`No such file or directory`) |
| branch | `uv sync && uv run pytest` | 37 passed, 24 skipped (first commit) |
| branch, later | `env -u STATS19_DOWNLOAD_DIRECTORY uv run pytest` | 54 passed, 24 skipped |
| branch, later | `STATS19_DOWNLOAD_DIRECTORY=$LAKE uv run pytest` | 78 passed |

## Embedded data

`uv run python scripts/build_schema.py --write` exports from the installed R
stats19 4.2.0. Output is byte-identical to a direct export from the dev
checkout `~/github/ropensci/stats19` (`6047da0`, also 4.2.0). Rows: schema
1821, variables 111, file names 26. The previous golden `schema.csv` had
1820 rows. The extra row is `junction_detail` code 19 "Other junction",
which the 2025 DfT data guide (`2024_code_list` sheet) also lists.

## Before and after, same probe, offline

Probe: `scripts/offline_probe.py`, `STATS19_DOWNLOAD_DIRECTORY=$LAKE`.

| call | before (`e71a229`) | after |
|------|-------------------|-------|
| `get_casualties(2019)` | 153158 rows, 42.2 s, 8824 MB peak RSS | 153158 rows, 1.0 s, 1228 MB |
| `get_vehicles(2019)` | tried to download `vehicle-1979-latest-published-year.csv` | `OfflineError` naming that file (with `STATS19_OFFLINE=1`) |
| `get_collisions(5)` | 9116625 rows (the whole 1979 history), 58.7 s, 11833 MB | `OfflineError`: `collision-last-5-years.csv` not on disk |

The two `get_casualties(2019)` frames have identical values.
`casualty_distance_banding` is entirely empty for 2019. pandas types it as
`str` when it parses the whole history and `float64` when it parses the
2019 slice. No other column differs in dtype.

## Lake against the embedded manifest

`stats19 check --data-dir $LAKE`

On disk, not in the manifest (10): `accident-2017`, `accident-2018`,
`accident-2019`, `accident-2020`, `accident-last-5-years`,
`casualty-1979-2021`, `casualty-2017`, `casualty-2019`, `casualty-2020`,
`vehicle-2017`.

In the manifest, not on disk (9): `casualties-adjustment-last-5-years`,
`casualty-adjustment-lookup_2004-latest-published-year`,
`casualty-last-5-years`, `collision-adjustment-last-5-years`,
`collision-adjustment-lookup_2004-latest-published-year`,
`collision-last-5-years`, `historical-revisions-data`,
`vehicle-1979-latest-published-year`, `vehicle-last-5-years`.

Other differences found:

- Old files (`accident-*`, `casualty-2017/2019/2020`, `casualty-1979-2021`,
  `vehicle-2017`) start with a UTF-8 BOM and use `accident_*` names.
- `accident-last-5-years.csv` covers 2017 to 2021, so it is a stale
  "last 5 years". It is never used for a `year=5` request.
- `casualty-1979-latest-published-year.csv` has `escooter_flag`. The
  per-year casualty files do not.
- `casualty_type` code 33 appears in 6103 rows (2020 to 2025) but is in
  neither the R schema nor the 2025 DfT guide. 6015 of those rows have
  `escooter_flag` 1. The layer maps it to e-scooter.
- No per-year casualty file for 2018, and no vehicle data at all for
  2018 to 2020.
- R `find_file_name(5)` returns the 1979 history because `5 < 2021`. The
  last-5-years branch is unreachable for the number 5. Fixed in this port.

## Casualty layer

`STATS19_OFFLINE=1 unshare -rn uv run --offline stats19 casualties --years 2019-2024 --authority E08000035 --out /tmp/s19x/leeds --data-dir $LAKE`
1.33 s, 1645 MB peak RSS. Leeds 2024: 1463 collisions, 1898 casualties.

An independent check from the raw CSVs (DuckDB, not using the layer code)
matched per-year collisions, casualties, fatal, serious and slight counts,
cyclist counts and 2019 adjusted KSI (453.03) for 2019 to 2024, with no
differences. Per-year 2024 files and the 1979 file agree for Leeds 2024.
