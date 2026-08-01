"""Diagnose mismatches with keep_default_na=False on both sides."""

from __future__ import annotations

import pandas as pd

from stats19 import read


def load_ref(table: str, year: int) -> pd.DataFrame:
    return pd.read_csv(
        f"scripts/reference/reference_{table}_{year}.csv",
        low_memory=False,
        keep_default_na=False,
    ).replace("", pd.NA)


n = 500
for table in ["collision", "casualty", "vehicle"]:
    ref = load_ref(table, 2024)
    readers = {
        "collision": read.read_collisions,
        "casualty": read.read_casualties,
        "vehicle": read.read_vehicles,
    }
    py = readers[table](year=2024)
    print(f"\n=== {table} 2024 ===")
    for col in ref.columns:
        if col not in py.columns:
            print(f"{col:<45} MISSING in py")
            continue
        a = ref[col].iloc[:n]
        b = py[col].iloc[:n]
        na_a = a.isna() | (a.astype(str).str.strip() == "")
        na_b = b.isna() | (b.astype(str).str.strip() == "")
        a_s = a.astype(str).fillna("").str.strip()
        b_s = b.astype(str).fillna("").str.strip()
        eq = (a_s == b_s) | (na_a & na_b)
        mm = int((~eq).sum())
        if mm > 0:
            idx = (~eq).to_numpy().nonzero()[0][:2]
            examples = [(str(a.iloc[i]), str(b.iloc[i])) for i in idx]
            print(f"{col:<45} {str(b.dtype):<12} {mm / n * 100:5.1f}%  {examples}")
