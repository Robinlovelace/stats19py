# stats19py — Python port of the R `stats19` package

Pure-Python implementation, from first principles, mirroring the API and behaviour of
the [ropensci/stats19](https://github.com/ropensci/stats19) R package (v4.1.0-dev).

- **Repo:** `Robinlovelace/stats19py` (this repo) — code lives here, separate from the R package
- **PyPI name:** `stats19` (free as of 2026-08-01; `pystats19` is taken by a stalled third-party port)
- **License:** GPL-3.0-or-later (matches the R package)
- **Stack:** Python 3.11+, `uv` for env/pkg management, `ruff` for lint+format,
  Pylance (standard mode) + pyright for type checking, pytest for TDD.
- **Data layer:** pandas (DataFrame) + DuckDB (optional ingestion engine, mirrors R `engine = "duckdb"`, PR #307)

## Ground truth & known divergences (verified 2026-08-01)

- DfT data served from `https://data.dft.gov.uk/road-accidents-safety-data/`
- **R v4.0.0 (installed/CRAN) returns `*-provisional-mid-year-unvalidated-2025.csv` filenames that 404 on DfT.**
  Fixed in dev v4.1.0 (PR #316) to plain `*-2025.csv` (which return 200). Python port follows
  **v4.1.0-dev + live DfT** behaviour. → issue candidate for ropensci/stats19 (released 4.0.0 broken for 2025).
- `find_file_name("all")` in installed v4.0.0 returns `character(0)` (bug); dev code intends 1979-latest files.
- `file_names.rda` (26 names) is the authoritative filename list; Python embeds its own copy,
  regenerated from the same source, and can refresh from DfT.

## Vertical slices (each end-to-end, checkpointed)

Each slice is independently usable and reviewable; all use red-green TDD.

| Slice | Scope | Checkpoint (definition of done) |
|-------|-------|--------------------------------|
| **1** | Package skeleton + file discovery (`list_files()`, `find_file_name()`, `get_url()`, `get_data_directory()`/`set_data_directory()`) | `uv run pytest` green; Python enumerates same 2024/2025 filenames as R; URLs hit 200 |
| **2** | Download (`dl_stats19()` equivalent) | 2024/2025 CSVs on disk in data dir; byte-count matches R `dl_stats19()`; offline tests use a local HTTP stub |
| **3** | Read (`read_collisions()`, `read_casualties()`, `read_vehicles()`) | Column names, dtypes, row counts for 2024/2025 match R output (comparison harness) |
| **4** | Format (`format_collisions()`, `format_casualties()`, `format_vehicles()`, `format_column_names()`) | Code→label lookups from embedded schema match R `format_*()` on 2024/2025; fuzzy compare |
| **5** | R↔Python comparison harness | Script runs R and Python on 2024/2025, diffs outputs/dtypes/spot values; report produced; diffs triaged to issues | ✅ |
| **6** | `get_stats19()` end-to-end + multi-year + joins + **DuckDB Spatial** | Full pipeline for 2024+2025; joins match R; `format_sf()`/GeoParquet via DuckDB spatial (not geopandas); e-scooter rider unification | ✅ |
| **7** | Cleaning (`clean_make()` etc.), adjustments, MOT/ULEZ | Checkpoint per sub-feature; parity with R on sample data | ⬜ |

## Comparison & issue workflow

- `scripts/compare_r_python.py` + `scripts/reference_from_r.R` — produce R reference outputs
  (CSV + dtype manifest) for 2024/2025, run Python equivalents, diff.
- Differences triaged:
  - Python bug → fix here (TDD)
  - R bug → open issue in `ropensci/stats19` (e.g. the 2025 provisional filename bug, found 2026-08-01)
  - Data/spec ambiguity → document + issue in the repo that owns the behaviour

## Schema & provenance (golden file)

`schema.csv` (repo root, visible) + `src/stats19/data/stats19_schema.csv` (runtime copy)
is the **golden schema**: 1820 rows of `table/variable/code/label/note/type`.

- **Source of truth:** `ropensci/stats19` v4.1.0-dev package data (`stats19_schema.rda`,
  `stats19_variables.rda`). Chosen for behavioural parity: the schema carries R quirks
  that must be preserved (e.g. literal `"None"` labels for code 0 in 6 variables).
- **Open-access alternative (cross-validation):** DfT publishes the official
  `dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2025.xlsx`,
  sheet `2024_code_list` (1821 rows) — the authoritative public code list. It
  overlaps the golden schema by ~1776/1818 keys. See `scripts/compare_dft_schema.py`.
  Divergences found: DfT has empty label where R has `"None"` (code 0, 6 vars);
  DfT labels carry trailing whitespace. → issue candidates for ropensci/stats19.
- **Regenerate:** `uv run python scripts/build_schema.py --write` (re-exports from the
  R dev checkout, writes provenance JSON, refreshes the root copy).
- **Provenance:** `src/stats19/data/schema_provenance.json` records source, date,
  and cross-validation results.

## Development

```bash
uv sync                    # create env, install deps
uv run pytest              # run tests (red-green TDD)
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pyright             # type check (Pylance-standard strictness)
uv run python -c "import stats19; print(stats19.list_files(2024))"
```
