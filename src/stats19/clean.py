"""Data cleaning functions for STATS19 vehicle data (R package clean.R).

Ports of ``extract_make_stats19()``, ``clean_make()``, ``clean_model()`` and
``clean_make_model()``. All are pure string transformations on the DfT
``generic_make_model`` field, so they are fully testable offline.
"""

from __future__ import annotations

import re

import pandas as pd

#: Multi-word makes matched by prefix, in priority order (R case_when order).
_MULTIWORD_MAKES: list[tuple[str, str]] = [
    ("ALFA ROMEO", "ALFA ROMEO"),
    ("ASTON MARTIN", "ASTON MARTIN"),
    ("AUSTIN MORRIS", "AUSTIN MORRIS"),
    ("LAND ROVER", "LAND ROVER"),
    ("RANGE ROVER", "LAND ROVER"),
    ("LONDON TAXIS", "LONDON TAXIS INTERNATIONAL"),
    ("JOHN DEERE", "JOHN DEERE"),
    ("NEW HOLLAND", "NEW HOLLAND"),
    ("ALEXANDER DENNIS", "ALEXANDER DENNIS"),
    ("ROYAL ENFIELD", "ROYAL ENFIELD"),
    ("ROLLS ROYCE", "ROLLS ROYCE"),
    ("MASSEY FERGUSON", "MASSEY FERGUSON"),
    ("LEYLAND DAF", "LEYLAND DAF"),
    ("DAF TRUCKS", "DAF"),
    ("LEYLAND CARS MINI", "MINI"),
    ("IVECO FORD", "IVECO"),
    ("FREIGHT ROVER", "FREIGHT ROVER"),
]

#: Makes kept in their all-caps form (R case_when first branch).
_UPPERCASE_MAKES = frozenset(
    {
        "GM",
        "BYD",
        "VW",
        "NIO",
        "ORA",
        "IM",
        "MG",
        "MINI",
        "EV",
        "EV6",
        "EV9",
        "EQC",
        "EQB",
        "EQA",
        "EQE",
        "XPENG",
        "CUPRA",
        "DS",
        "GEELY",
        "SAIC",
        "BMW",
        "DAF",
        "KTM",
        "MAN",
        "VDL",
        "LEVC",
        "ERF",
        "LDV",
        "MCW",
        "JCB",
        "MZ",
        "MCC",
        "BSA",
        "TVR",
        "CZ",
        "MBK",
        "AJS",
        "CPI",
        "PGO",
    }
)

#: Values treated as missing/NA after extraction (R clean_make).
_NA_MAKES = frozenset(
    {"-1", "Make", "Other", "Generic", "All", "Better", "Easy", "David", "White", "Int.", "Data"}
)

#: Model strings that are invalid -> NA (R clean_model).
_INVALID_MODELS = frozenset({"AND MODEL REDACTED", "MISSING OR OUT OF RANGE", "MODEL UNKNOWN"})

#: Model names kept uppercase (R clean_model).
_UPPERCASE_MODELS = frozenset({"CBR", "RS", "SQ", "GS", "BZ4X", "BZ2X", "BZ1X"})


def _str_to_title(s: str) -> str:
    """Mirror R stringr::str_to_title (ICU title-case rules).

    Within each maximal run of letters+digits, the first letter is
    capitalised and every other letter lowercased. Digits neither start a
    new word nor stop the lowercasing: "500X" -> "500x", "A1B2" -> "A1b2",
    "X500" -> "X500". This differs from Python's ``str.title()``, which
    treats every character after a non-letter (incl. digits) as a word start.
    """
    out: list[str] = []
    in_word = False
    seen_first = False
    for ch in s:
        if ch.isalnum():
            if not in_word:
                in_word = True
                seen_first = False
            if not seen_first:
                seen_first = True
                out.append(ch.upper() if ch.isalpha() else ch)
            elif ch.isalpha():
                out.append(ch.lower())
            else:
                out.append(ch)  # digit inside word: unchanged
        else:
            in_word = False
            seen_first = False
            out.append(ch)
    return "".join(out)


#: Mercedes "Class" model regex (R: ^(Cla|Gla|Clk|Cls|Cle|Eqa|Eqb|Eqc|Eqe|Sl[ck]|Amg)\s*Class$)
_MERC_CLASS_RE = re.compile(
    r"^(Cla|Gla|Clk|Cls|Cle|Eqa|Eqb|Eqc|Eqe|Sl[ck]|Amg)\s*Class$", re.IGNORECASE
)


def _normalise(s: str) -> str:
    """Uppercase, strip parentheticals and trim (R stringr steps)."""
    s = s.upper()
    s = re.sub(r"\s*\([^)]+\)", "", s)
    return s.strip()


def extract_make_stats19(generic_make_model: pd.Series) -> pd.Series:
    """Extract vehicle make from generic make/model strings (R extract_make_stats19).

    Handles multi-word makes first, then falls back to the first word.
    """
    out = generic_make_model.map(_normalise)
    matched = pd.Series(False, index=out.index)
    for prefix, make in _MULTIWORD_MAKES:
        mask = out.str.startswith(prefix, na=False) & ~matched
        out.loc[mask] = make
        matched = matched | mask
    # Default: first word (only for rows that matched no multi-word prefix)
    sub = out.loc[~matched]
    first_word = sub.str.split(" ", n=1, expand=True)[0]
    out.loc[~matched] = first_word.values
    return out


def clean_make(make: pd.Series, extract_make: bool = True) -> pd.Series:
    """Clean vehicle makes (R ``clean_make()``)."""
    if extract_make:
        make = extract_make_stats19(make)

    # Title-case everything except the all-caps brands
    out = make.map(lambda v: v if v in _UPPERCASE_MAKES else _str_to_title(str(v)))

    def _fix(v: str) -> str | None:
        if v in _NA_MAKES:
            return None
        if re.search(r"Volksw|VW", v, re.IGNORECASE):
            return "Volkswagen"
        if "Citro" in v:
            return "Citroen"
        if "Merc" in v:
            return "Mercedes"
        if "Range Rover" in v:
            return "Land Rover"
        if "Geely" in v:
            return "Geely"
        if re.search(r"oda|Oda", v):
            return "Skoda"
        if v == "Daf":
            return "DAF"
        if v == "Leyland Daf":
            return "DAF"
        if v == "Dennis":
            return "Alexander Dennis"
        if v == "Case":
            return "Case IH"
        if v in ("London Taxis Int", "London Taxis International"):
            return "London Taxis International"
        if v == "Ssangyong":
            return "SsangYong"
        if v in ("Smart", "smart"):
            return "smart"
        if v == "Mini":
            return "MINI"
        if v == "Iveco-Ford":
            return "Iveco"
        if v == "Enfield":
            return "Royal Enfield"
        if re.search(r"Man/Vw", v, re.IGNORECASE):
            return "MAN"
        if v == "Int.":
            return "International"
        if v in ("Freight", "Freight Rover"):
            return "Freight Rover"
        if v == "Austin Morris":
            return "Austin Morris"
        if "Redacted" in v:
            return None
        return v

    return out.map(_fix)


def clean_model(model: pd.Series) -> pd.Series:
    """Clean vehicle models (R ``clean_model()``).

    Extracts the make, removes it from the string, and title-cases the rest.
    """
    upper = model.map(_normalise)
    make_part = extract_make_stats19(upper)

    def _extract(v: str, m: str) -> str | None:
        if m is None or (isinstance(m, float) and pd.isna(m)):
            return None
        rest = v[len(m) + 1 :] if len(v) > len(m) else ""
        rest = re.sub(r"^TRUCKS\s*", "", rest).strip()
        return rest or None

    out = pd.Series(
        [
            _extract(str(v), str(m)) if not pd.isna(v) else None
            for v, m in zip(upper, make_part, strict=False)
        ],
        index=model.index,
        dtype="object",
    )

    # Vectorised invalid-string masking (R clean_model)
    invalid = upper.str.contains("REDACTED", na=False) | out.str.contains(
        "MISSING", na=False, regex=False
    )
    invalid = invalid | out.isin(_INVALID_MODELS)
    out = out.where(~invalid)

    # Whole-number normalisation: "1.0" -> "1"
    whole = out.str.match(r"^[0-9]+\.0$", na=False)
    out = out.where(~whole, out.str.replace(r"\.0$", "", regex=True))

    # Title-case unless in the uppercase set (R str_to_title semantics)
    def _case(v: object) -> object:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return v if v in _UPPERCASE_MODELS else _str_to_title(str(v))

    out = out.map(_case)

    # Mercedes "Class" models lowercased
    merc = out.map(
        lambda v: (
            bool(_MERC_CLASS_RE.match(str(v)))
            if v is not None and not (isinstance(v, float) and pd.isna(v))
            else False
        )
    )
    out = out.where(~merc, out.map(lambda v: str(v).lower() if v is not None else None))

    # LandCruiser capitalisation
    out = out.map(
        lambda v: (
            str(v).replace("Landcruiser", "LandCruiser")
            if v is not None and not (isinstance(v, float) and pd.isna(v))
            else None
        )
    )
    return out


def clean_make_model(generic_make_model: pd.Series) -> pd.Series:
    """Combined clean make + model (R ``clean_make_model()``)."""
    make = clean_make(generic_make_model)
    model = clean_model(generic_make_model)
    res = make.astype(str) + " " + model.astype(str)
    res = res.str.replace(" NA", "", regex=False).str.replace("NA ", "", regex=False)
    res = res.where(res.ne("NA"))
    return res
