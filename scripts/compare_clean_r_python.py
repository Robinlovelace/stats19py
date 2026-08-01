"""Compare Python clean_make/clean_model vs R on real 2024 vehicle data.

Loads a sample of generic_make_model values from the 2024 vehicle CSV,
runs both implementations, and reports mismatches.
"""

from __future__ import annotations

import subprocess
import tempfile

import pandas as pd

from stats19 import clean

raw = pd.read_csv(
    "data/dft-road-casualty-statistics-vehicle-2024.csv",
    usecols=["generic_make_model"],
    low_memory=False,
)
s = raw["generic_make_model"].dropna().astype(str).head(2000).tolist()

py_make = clean.clean_make(pd.Series(s)).fillna("NA").tolist()
py_model = clean.clean_model(pd.Series(s)).fillna("NA").tolist()

# pass the values to R via a temp CSV (robust for large vectors)
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
    f.write("\n".join(s))
    tmp = f.name
r_code = f"""
v <- readLines("{tmp}")
suppressMessages(pkgload::load_all("~/github/ropensci/stats19", quiet = TRUE))
m <- clean_make(v); mo <- clean_model(v)
m[is.na(m)] <- "NA"; mo[is.na(mo)] <- "NA"
cat(paste(m, collapse = "\\x01"), "\\n")
cat(paste(mo, collapse = "\\x01"), "\\n")
"""
out = subprocess.run(["Rscript", "-e", r_code], capture_output=True, text=True, check=True)
r_make, r_model = out.stdout.strip().split("\n")
r_make = r_make.split("\x01")
r_model = r_model.split("\x01")
# R's cat() may append a trailing space to the last element; strip both sides
r_make = [x.strip() for x in r_make]
r_model = [x.strip() for x in r_model]
print(
    "lengths: "
    f"py_make={len(py_make)} r_make={len(r_make)} "
    f"py_model={len(py_model)} r_model={len(r_model)}"
)

nm = sum(1 for a, b in zip(py_make, r_make) if a != b)
nmo = sum(1 for a, b in zip(py_model, r_model) if a != b)
print(f"make mismatch: {nm}/{len(s)}")
for i, (a, b) in enumerate(zip(py_make, r_make)):
    if a != b:
        print(f"  row {i}: {s[i]!r} -> py={a!r} r={b!r}")
        if nm > 8:
            break
print(f"model mismatch: {nmo}/{len(s)}")
shown = 0
for i, (a, b) in enumerate(zip(py_model, r_model)):
    if a != b:
        print(f"  row {i}: {s[i]!r} -> py={a!r} r={b!r}")
        shown += 1
        if shown > 25:
            break
