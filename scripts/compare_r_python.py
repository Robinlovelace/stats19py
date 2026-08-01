#!/usr/bin/env python3
"""Compare Python stats19 output against R reference output (Slice 5 harness).

Usage:
    uv run python scripts/compare_r_python.py --table collision --year 2024
    uv run python scripts/compare_r_python.py            # all tables x 2024,2025

Reads R references from scripts/reference/reference_<table>_<year>.csv and
compares against stats19.read_* on the same year. Reports row/col counts,
column-name matches, dtype matches, and value-level concordance on a sample.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from stats19 import (
    read_casualties,
    read_collisions,
    read_vehicles,
)

REPO = Path(__file__).resolve().parents[1]
REF_DIR = REPO / "scripts" / "reference"


def load_reference(table: str, year: int) -> pd.DataFrame:
    # keep_default_na=False: R may write the literal string "None" (schema
    # labels) which pandas would otherwise convert to NaN. R's write.csv
    # writes missing values as the literal string "NA" -> map to NA.
    df = pd.read_csv(
        REF_DIR / f"reference_{table}_{year}.csv", low_memory=False, keep_default_na=False
    )
    df = df.replace("", pd.NA).replace("NA", pd.NA)
    return df


def compare(table: str, year: int) -> dict:
    ref = load_reference(table, year)
    readers = {
        "collision": read_collisions,
        "casualty": read_casualties,
        "vehicle": read_vehicles,
    }
    py = readers[table](year=year)  # formatted (format=True)
    if py is None:
        return {"table": table, "year": year, "error": "python read returned None"}

    report: dict = {
        "table": table,
        "year": year,
        "r_rows": len(ref),
        "py_rows": len(py),
        "r_cols": len(ref.columns),
        "py_cols": len(py.columns),
    }

    # Column names: R writes names as-is; Python uses snake_case
    r_names = list(ref.columns)
    py_names = list(py.columns)
    report["names_exact_match"] = r_names == py_names
    report["r_only"] = [c for c in r_names if c not in py_names][:20]
    report["py_only"] = [c for c in py_names if c not in r_names][:20]

    # Value concordance on shared columns (sample rows)
    shared = [c for c in r_names if c in py_names]
    n_check = min(500, len(ref), len(py))
    mismatches = 0
    checked = 0
    mismatch_cols: dict[str, int] = {}
    for col in shared:
        a = ref[col].iloc[:n_check]
        b = py[col].iloc[:n_check]
        na_a = a.isna() | (a.astype(str).str.strip() == "")
        na_b = b.isna() | (b.astype(str).str.strip() == "")

        # Numeric columns: compare as float (R write.csv + pandas re-read
        # turns ints into floats, e.g. "2024" vs "2024.0")
        if pd.api.types.is_numeric_dtype(a) or pd.api.types.is_numeric_dtype(b):
            a_num = pd.to_numeric(a, errors="coerce")
            b_num = pd.to_numeric(b, errors="coerce")
            eq = (a_num == b_num) | (na_a & na_b)
        else:
            a_s = a.astype(str).fillna("").str.strip()
            b_s = b.astype(str).fillna("").str.strip()
            eq = (a_s == b_s) | (na_a & na_b)
        mm = int((~eq).sum())
        mismatches += mm
        checked += n_check
        if mm:
            mismatch_cols[col] = mm
    report["checked_cells"] = checked
    report["mismatch_cells"] = mismatches
    report["concordance"] = 1 - mismatches / checked if checked else None
    report["mismatch_cols"] = mismatch_cols

    # Type-level comparison (python dtypes vs R classes written in meta)
    meta = pd.read_csv(REF_DIR / f"meta_{table}_{year}.csv")
    r_classes = meta["classes"].iloc[0].split(",")
    r_names_m = meta["column_names"].iloc[0].split(",")
    py_dtypes = {c: str(py[c].dtype) for c in py.columns}
    report["dtype_map"] = {c: py_dtypes.get(c) for c in r_names_m[:10]}
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=["collision", "casualty", "vehicle"], default=None)
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args()

    tables = [args.table] if args.table else ["collision", "casualty", "vehicle"]
    years = [args.year] if args.year else [2024, 2025]

    for t in tables:
        for y in years:
            r = compare(t, y)
            status = (
                "OK "
                if r.get("concordance", 0) is not None and r["concordance"] >= 0.99
                else "DIFF"
            )
            print(
                f"[{status}] {t} {y}: R {r['r_rows']}x{r['r_cols']} | "
                f"Py {r['py_rows']}x{r['py_cols']} | names_match={r['names_exact_match']} | "
                f"concordance={r.get('concordance')} | mismatches={r.get('mismatch_cells')}"
            )
            if r.get("r_only"):
                print(f"        R-only cols: {r['r_only']}")
            if r.get("py_only"):
                print(f"        Py-only cols: {r['py_only']}")
            if r.get("mismatch_cols"):
                print(f"        mismatch cols: {r['mismatch_cols']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
