"""Row-level comparison: DfT official code list vs golden schema."""

from __future__ import annotations

import openpyxl
import pandas as pd

from stats19 import read

wb = openpyxl.load_workbook("/tmp/dft_data_guide_2025.xlsx", read_only=True)
ws = wb["2024_code_list"]
rows = list(ws.iter_rows(values_only=True))
dft = pd.DataFrame(rows[1:], columns=[str(h) for h in rows[0]]).rename(
    columns={"field name": "variable", "code/format": "code"}
)
for c in ["code", "label"]:
    dft[c] = dft[c].astype(str).replace({"None": "", "nan": ""})
dft["code"] = dft["code"].str.strip()

s = read.schema()
s = s.copy()
for c in ["code", "label"]:
    s[c] = s[c].fillna("").astype(str).str.strip()


# Build keyed maps
def keyed(df: pd.DataFrame) -> dict:
    m = {}
    for _, r in df.iterrows():
        m[(r["table"], r["variable"], r["code"])] = r["label"]
    return m


dft_map = keyed(dft)
s_map = keyed(s)

dft_keys = set(dft_map)
s_keys = set(s_map)

print(f"DfT entries: {len(dft_keys)}  |  Golden schema entries: {len(s_keys)}")
print(f"Keys in both: {len(dft_keys & s_keys)}")
print(f"DfT only (not in golden): {len(dft_keys - s_keys)}")
print(f"Golden only (not in DfT): {len(s_keys - dft_keys)}")

# label disagreements on shared keys
disagree = [(k, dft_map[k], s_map[k]) for k in dft_keys & s_keys if dft_map[k] != s_map[k]]
print(f"\nLabel disagreements on shared keys: {len(disagree)}")
for k, dl, sl in disagree[:15]:
    print(f"  {k}: DfT={dl!r} vs schema={sl!r}")

# Show DfT-only sample
print("\nSample DfT-only keys:")
for k in sorted(dft_keys - s_keys)[:10]:
    print(f"  {k}: {dft_map[k]!r}")
print("\nSample golden-only keys:")
for k in sorted(s_keys - dft_keys)[:10]:
    print(f"  {k}: {s_map[k]!r}")
