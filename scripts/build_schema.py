#!/usr/bin/env python3
"""Build/verify the golden stats19 schema for this package.

The golden schema (code->label lookups + per-variable types) is the heart of
the package. Sources, in priority order:

1. **ropensci/stats19 R package data** (authoritative for behaviour parity):
   `data/stats19_schema.rda` + `data/stats19_variables.rda` from the dev
   checkout (v4.1.0-dev). This is the source of truth because the whole point
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
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG_DATA = REPO / "src" / "stats19" / "data"
SCHEMA_PATH = PKG_DATA / "stats19_schema.csv"
VARIABLES_PATH = PKG_DATA / "stats19_variables.csv"
PROV_PATH = PKG_DATA / "schema_provenance.json"
GOLDEN_PATH = REPO / "schema.csv"

STATS19_DEV = Path.home() / "github" / "ropensci" / "stats19"

_EXPORT_R = """
suppressMessages(pkgload::load_all("{dev}", quiet = TRUE))
load(file.path("{dev}", "data", "stats19_schema.rda"))
load(file.path("{dev}", "data", "stats19_variables.rda"))
write.csv(stats19_schema, "{schema}", row.names = FALSE, na = "")
write.csv(stats19_variables, "{variables}", row.names = FALSE, na = "")
cat("exported", nrow(stats19_schema), "schema rows,", nrow(stats19_variables), "variable rows\\n")
"""


def export_from_r() -> tuple[int, int]:
    """Re-export schema + variables from the R dev package."""
    if not (STATS19_DEV / "DESCRIPTION").exists():
        raise FileNotFoundError(f"R stats19 dev checkout not found at {STATS19_DEV}")
    r_script = _EXPORT_R.format(
        dev=STATS19_DEV, schema=SCHEMA_PATH, variables=VARIABLES_PATH
    )
    out = subprocess.run(
        ["Rscript", "-e", r_script], capture_output=True, text=True, check=True
    )
    print(out.stdout.strip())
    return 0, 0


def write_provenance(n_rows: int) -> None:
    prov = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": {
            "r_package": "ropensci/stats19",
            "r_version": "v4.1.0-dev (master after PR #316)",
            "path": str(STATS19_DEV / "data"),
            "files": ["stats19_schema.rda", "stats19_variables.rda"],
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
    args = ap.parse_args()

    if args.write:
        export_from_r()
        import pandas as pd  # noqa: PLC0415

        n = len(pd.read_csv(SCHEMA_PATH))
        write_provenance(n)
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
