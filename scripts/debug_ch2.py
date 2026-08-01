"""Pinpoint the exact carriageway_hazards mismatch rows."""

from __future__ import annotations

import pandas as pd

from stats19 import read

ref = pd.read_csv("scripts/reference/reference_collision_2024.csv", low_memory=False)
py = read.read_collisions(year=2024)

n = 500
a = ref["carriageway_hazards"].iloc[:n]
b = py["carriageway_hazards"].iloc[:n]
na_a = a.isna() | (a.astype(str).str.strip() == "")
na_b = b.isna() | (b.astype(str).str.strip() == "")
a_s = a.astype(str).fillna("").str.strip()
b_s = b.astype(str).fillna("").str.strip()
eq = (a_s == b_s) | (na_a & na_b)
mm_idx = (~eq).to_numpy().nonzero()[0]
print("mismatch rows:", mm_idx.tolist())
for i in mm_idx:
    print(f"row {i}: R={a.iloc[i]!r}  Py={b.iloc[i]!r}")

# what code is in the raw file for those rows?
raw = pd.read_csv(
    "data/dft-road-casualty-statistics-collision-2024.csv",
    usecols=["carriageway_hazards"],
    dtype={"carriageway_hazards": str},
)
print("\nraw codes at those rows:", raw["carriageway_hazards"].iloc[mm_idx].tolist())

# check the -1 handling: R treats -1 as NA at read; our schema maps -1 -> label?
s = read.schema()
neg = s[(s["variable"] == "carriageway_hazards") & (s["code"] == "-1")]
print("\nschema -1 mapping:", neg[["code", "label"]].to_dict("records"))
