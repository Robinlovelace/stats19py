"""Investigate carriageway_hazards label mismatch."""

from __future__ import annotations

import pandas as pd

from stats19 import read

s = read.schema()
ch = s[s["variable"] == "carriageway_hazards"][["code", "label"]]
print("lookup entries with 'unknown':")
print(ch[ch["label"].str.contains("unknown", na=False)].to_string())

# what's in the raw file?
raw = pd.read_csv(
    "data/dft-road-casualty-statistics-collision-2024.csv",
    usecols=["carriageway_hazards"],
    dtype={"carriageway_hazards": str},
)
vals = raw["carriageway_hazards"].value_counts(dropna=False)
print("\nraw carriageway_hazards value counts:")
print(vals.head(10))
print("\n-1 count:", int((raw["carriageway_hazards"] == "-1").sum()))
print("99 count:", int((raw["carriageway_hazards"] == "99").sum()))
