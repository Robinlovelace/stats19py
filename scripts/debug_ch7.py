"""Check schema entries for both carriageway hazard columns."""

from __future__ import annotations

from stats19 import read

s = read.schema()
for var in ["carriageway_hazards", "carriageway_hazards_historic"]:
    rows = s[s["variable"] == var][["code", "label"]]
    print(f"\n{var}: {len(rows)} entries")
    print(rows.to_string())
