"""Debug why code->label lookups fail in format_stats19."""

from __future__ import annotations

from stats19 import read

s = read.schema()
print("schema tables:", s["table"].unique())
print("schema variable types:", s["type"].unique())

# check the light_conditions lookup entries
lk = s[s["variable"] == "light_conditions"][["code", "label"]].dropna(subset=["code"])
print("\nlight_conditions lookup:")
print(lk.to_string())
print("code dtypes:", lk["code"].dtype, "| sample:", lk["code"].head(3).tolist())

# what does the raw read produce for light_conditions?
raw = read.read_collisions(year=2024, format=False)
print("\nraw light_conditions dtype:", raw["light_conditions"].dtype)
print("raw sample:", raw["light_conditions"].head(5).tolist())

# what does formatted produce?
fmt = read.read_collisions(year=2024)
print("\nformatted light_conditions dtype:", fmt["light_conditions"].dtype)
print("formatted sample:", fmt["light_conditions"].head(5).tolist())
