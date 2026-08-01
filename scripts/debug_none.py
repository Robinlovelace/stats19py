"""Count literal 'None' strings in the R schema (potential R data quirk)."""

from __future__ import annotations

import pandas as pd

# R exports NA as empty string (write.csv na=""); "None" is a literal string
df = pd.read_csv(
    "src/stats19/data/stats19_schema.csv",
    dtype=str,
    keep_default_na=False,
)
n_none = int((df["label"] == "None").sum())
n_empty = int((df["label"] == "").sum())
print(f"labels == 'None' (literal): {n_none}")
print(f"labels == '' (R NA): {n_empty}")
print("variables with 'None' labels:")
print(df.loc[df["label"] == "None", ["table", "variable", "code"]].to_string())
