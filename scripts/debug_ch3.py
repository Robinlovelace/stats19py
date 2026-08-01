"""Check for duplicate codes in the schema lookup."""

from __future__ import annotations

from stats19 import read

s = read.schema()
# all duplicate (variable, code) pairs
dup = s.groupby(["variable", "code"]).size().reset_index(name="n")
dup = dup[dup["n"] > 1]
print("duplicate (variable, code) pairs:", len(dup))
print(dup.head(10).to_string())

ch = s[s["variable"] == "carriageway_hazards"].copy()
ch["code"] = ch["code"].astype(str)
print("\ncarriageway_hazards rows with code '0':")
print(ch[ch["code"] == "0"][["code", "label"]].to_string())

# how the mapping is built in format.py: dict(zip(...)) — last wins
lookup = ch[["code", "label"]].dropna(subset=["code"])
mapping = dict(zip(lookup["code"], lookup["label"]))
print("\nfinal mapping['0'] =", repr(mapping.get("0")))
print("final mapping['99'] =", repr(mapping.get("99")))
