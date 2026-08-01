"""Check dtype + masking behaviour for road_type in refactored core."""

from __future__ import annotations

# replicate read + format up to masking
import importlib.resources as res

import pandas as pd

from stats19 import core, data

with res.files("stats19").joinpath("data", "file_names.txt").open() as f:
    pass
df = core._read_csv("data/dft-road-casualty-statistics-collision-2024.csv")
df.columns = core.format_column_names(list(df.columns))
df = core._normalize_collision_reference(df)
df = core.format_stats19(df, type="collision")

print("road_type dtype:", df["road_type"].dtype)
print("values:", df["road_type"].iloc[:5].tolist())
print("Unknown count:", int((df["road_type"] == "Unknown").sum()))
print("NA count:", int(df["road_type"].isna().sum()))
print("is_object:", pd.api.types.is_object_dtype(df["road_type"]))

# what does the lookup produce for code 9?
lk = data.lookups("collision")["road_type"]
print("code 9 ->", repr(lk.get("9")))
print("'Unknown' in missing:", "Unknown" in core._MISSING_LABELS)
