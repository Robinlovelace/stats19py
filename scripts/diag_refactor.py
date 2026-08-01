"""Diagnose mismatches after refactor (2024 data)."""

from __future__ import annotations

import pandas as pd

from stats19 import read_collisions, read_vehicles

n = 500
for table, reader in [("collision", read_collisions), ("vehicle", read_vehicles)]:
    ref = (
        pd.read_csv(
            f"scripts/reference/reference_{table}_2024.csv",
            low_memory=False,
            keep_default_na=False,
        )
        .replace("", pd.NA)
        .replace("NA", pd.NA)
    )
    py = reader(year=2024)
    assert py is not None
    print(f"\n=== {table} 2024 ===")
    for col in ref.columns:
        if col not in py.columns:
            continue
        a, b = ref[col].iloc[:n], py[col].iloc[:n]
        na_a = a.isna() | (a.astype(str).str.strip() == "")
        na_b = b.isna() | (b.astype(str).str.strip() == "")
        if pd.api.types.is_numeric_dtype(a) or pd.api.types.is_numeric_dtype(b):
            eq = (pd.to_numeric(a, errors="coerce") == pd.to_numeric(b, errors="coerce")) | (
                na_a & na_b
            )
        else:
            eq = (a.astype(str).fillna("").str.strip() == b.astype(str).fillna("").str.strip()) | (
                na_a & na_b
            )
        mm = int((~eq).sum())
        if mm:
            idx = (~eq).to_numpy().nonzero()[0][:2]
            print(f"{col:<40} {mm}  {[(str(a.iloc[i]), str(b.iloc[i])) for i in idx]}")
