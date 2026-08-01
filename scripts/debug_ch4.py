"""Trace the exact transformation of carriageway_hazards rows 91/221/464."""

from __future__ import annotations

from stats19 import read

raw = read.read_collisions(year=2024, format=False)
print("raw dtype:", raw["carriageway_hazards"].dtype)
print("raw values rows 91,221,464:", raw["carriageway_hazards"].iloc[[91, 221, 464]].tolist())

# apply just the lookup step
s = read.schema()
lk = s.loc[s["variable"] == "carriageway_hazards", ["code", "label"]].dropna(subset=["code"])
mapping = dict(zip(lk["code"].astype(str), lk["label"]))
print("mapping keys sample:", list(mapping.items())[:3])

col = raw["carriageway_hazards"].iloc[[91, 221, 464]]
as_str = col.astype(str)
print("as str:", as_str.tolist())
mapped = as_str.map(lambda val: mapping.get(val, val))
print("mapped:", mapped.tolist())
