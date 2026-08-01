"""Check formatted output vs manual trace for rows 91/221/464."""

from __future__ import annotations

from stats19 import read

fmt = read.read_collisions(year=2024)
print("formatted dtype:", fmt["carriageway_hazards"].dtype)
print("formatted rows 91,221,464:", fmt["carriageway_hazards"].iloc[[91, 221, 464]].tolist())

# count how many 'unknown (self reported)' in formatted

print(
    "unknown count in formatted:",
    int((fmt["carriageway_hazards"] == "unknown (self reported)").sum()),
)
print("NaN count:", int(fmt["carriageway_hazards"].isna().sum()))
