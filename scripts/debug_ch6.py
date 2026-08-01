"""Check raw historic column values at mismatch rows."""

from __future__ import annotations

import pandas as pd

from stats19 import read

raw = read.read_collisions(year=2024, format=False)
cols = [c for c in raw.columns if "carriageway" in c]
print("cols:", cols)
for i in [91, 221, 464]:
    print(f"row {i}: " + ", ".join(f"{c}={raw[c].iloc[i]!r}" for c in cols))

# what does R's raw read give for those rows?
# carriageway_hazards_historic codes in raw file
rawf = pd.read_csv(
    "data/dft-road-casualty-statistics-collision-2024.csv",
    usecols=["carriageway_hazards", "carriageway_hazards_historic"],
    dtype=str,
)
for i in [91, 221, 464]:
    r = rawf.iloc[i]
    print(
        f"rawfile row {i}: hazards={r['carriageway_hazards']!r} historic={r['carriageway_hazards_historic']!r}"
    )
