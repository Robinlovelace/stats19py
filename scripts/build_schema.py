#!/usr/bin/env python3
"""Build/verify the golden stats19 schema for this package.

The golden schema (code->label lookups + per-variable types) is the heart of
the package. Sources, in priority order:

1. **ropensci/stats19 R package data** (authoritative for behaviour parity):
   `stats19_schema`, `stats19_variables` and `file_names` from the installed
   package (4.2.0 at the time of writing), or from the dev checkout with --dev.
   This is the source of truth because the whole point
   of the Python port is byte-for-byte parity with R; the schema carries R's
   quirks (e.g. literal "None" labels for code 0 in 6 variables) that must be
   preserved.

2. **DfT official data guide** (cross-validation only): the published XLSX
   `dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2025.xlsx`
   sheet `2024_code_list` is the open-access authoritative code list. It
   overlaps the R schema by ~1776/1818 keys and is used to *check* the golden
   file and surface divergences (see scripts/compare_dft_schema.py).

Outputs:
- src/stats19/data/stats19_schema.csv   (package data, consumed at runtime)
- src/stats19/data/stats19_variables.csv
- src/stats19/data/file_names.txt         (filename manifest, 26 names)
- src/stats19/data/schema_provenance.json
- schema.csv                            (visible golden copy at repo root)

Usage:
    uv run python scripts/build_schema.py            # report provenance
    uv run python scripts/build_schema.py --write    # (re)generate from R
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG_DATA = REPO / "src" / "stats19" / "data"
SCHEMA_PATH = PKG_DATA / "stats19_schema.csv"
VARIABLES_PATH = PKG_DATA / "stats19_variables.csv"
PROV_PATH = PKG_DATA / "schema_provenance.json"
GOLDEN_PATH = REPO / "schema.csv"

STATS19_DEV = Path.home() / "github" / "ropensci" / "stats19"
FILE_NAMES_PATH = PKG_DATA / "file_names.txt"

# Default source: the installed R package (lazy data). Pass --dev to export from
# a source checkout instead. Both gave identical output for stats19 4.2.0.
_EXPORT_R = """
{load}
write.csv(stats19_schema, "{schema}", row.names = FALSE, na = "")
write.csv(stats19_variables, "{variables}", row.names = FALSE, na = "")
writeLines(unname(unlist(file_names)), "{file_names}")
cat("stats19", as.character(packageVersion("stats19", lib.loc = .libPaths())),
    "exported", nrow(stats19_schema), "schema rows,", nrow(stats19_variables),
    "variable rows,", length(file_names), "file names\\n")
"""
_LOAD_INSTALLED = (
    'data("stats19_schema", "stats19_variables", "file_names", package = "stats19")'
)
_LOAD_DEV = """
for (f in c("stats19_schema", "stats19_variables", "file_names")) {{
  load(file.path("{dev}", "data", paste0(f, ".rda")))
}}
"""


def export_from_r(dev: bool = False) -> None:
    """Export schema, variables and the filename manifest from R."""
    PKG_DATA.mkdir(parents=True, exist_ok=True)
    if dev:
        if not (STATS19_DEV / "DESCRIPTION").exists():
            raise FileNotFoundError(f"R stats19 dev checkout not found at {STATS19_DEV}")
        load = _LOAD_DEV.format(dev=STATS19_DEV)
    else:
        load = _LOAD_INSTALLED
    r_script = _EXPORT_R.format(
        load=load, schema=SCHEMA_PATH, variables=VARIABLES_PATH, file_names=FILE_NAMES_PATH
    )
    out = subprocess.run(["Rscript", "-e", r_script], capture_output=True, text=True, check=True)
    print(out.stdout.strip())


def write_provenance(n_rows: int, r_version: str) -> None:
    prov = {
        "generated": datetime.now(UTC).isoformat(),
        "source": {
            "r_package": "ropensci/stats19",
            "r_version": r_version,
            "files": ["stats19_schema", "stats19_variables", "file_names"],
        },
        "cross_validation": {
            "dft_guide": (
                "https://assets.publishing.service.gov.uk/media/6a63900b2dc18ebe4c3b2bc8/"
                "dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2025.xlsx"
            ),
            "overlap_keys": "~1776/1818 with DfT 2024_code_list",
            "known_divergence": (
                "DfT gives empty label for code 0 in 6 variables; R schema uses "
                "literal 'None'. R behaviour preserved for parity. Also DfT labels "
                "have trailing whitespace; R's are trimmed."
            ),
        },
        "n_rows": n_rows,
        "columns": ["table", "variable", "code", "label", "note", "type"],
        "notes": (
            "Golden schema for stats19py. Regenerate with: "
            "uv run python scripts/build_schema.py --write"
        ),
    }
    PROV_PATH.write_text(json.dumps(prov, indent=2) + "\n")
    print(f"Wrote provenance: {PROV_PATH}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Re-export from R and rewrite")
    ap.add_argument("--dev", action="store_true", help="Export from the dev checkout")
    args = ap.parse_args()

    if args.write:
        export_from_r(dev=args.dev)
        import pandas as pd  # noqa: PLC0415

        n = len(pd.read_csv(SCHEMA_PATH))
        ver = subprocess.run(
            ["Rscript", "-e", 'cat(as.character(packageVersion("stats19")))'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        write_provenance(n, f"{ver} ({'dev checkout' if args.dev else 'installed'})")
        # refresh visible golden copy at repo root
        import shutil  # noqa: PLC0415

        shutil.copy(SCHEMA_PATH, GOLDEN_PATH)
        print(f"Copied golden schema to {GOLDEN_PATH}")
    else:
        if not SCHEMA_PATH.exists():
            print(f"Golden schema missing: {SCHEMA_PATH}")
            return 1
        import pandas as pd  # noqa: PLC0415

        n = len(pd.read_csv(SCHEMA_PATH))
        print(f"Golden schema: {SCHEMA_PATH} ({n} rows)")
        if PROV_PATH.exists():
            prov = json.loads(PROV_PATH.read_text())
            print(f"Provenance (generated {prov['generated']}):")
            print(json.dumps(prov["source"], indent=2))
        else:
            print("No provenance file; run with --write to generate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
