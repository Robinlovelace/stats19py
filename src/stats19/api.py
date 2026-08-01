"""API-backed lookups: MOT (DVSA), ULEZ (TfL) and severity adjustments.

Ports of R ``get_MOT()``, ``get_ULEZ()`` and ``get_stats19_adjustments()``.

These functions call external APIs (DVSA MOT history, TfL ULEZ compliance)
so they require network access and, for MOT, an API key. They are included
for API parity with the R package but degrade gracefully when the API is
unavailable (returning a message, mirroring R's ``get_stats19_adjustments``).
"""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

import pandas as pd

#: Env var holding the DVSA MOT API key (R uses Sys.getenv("MOTKEY")).
_MOT_KEY_ENV = "MOTKEY"
_MOT_URL = "https://beta.check-mot.service.gov.uk/trade/vehicles/mot-tests"
_ULEZ_URL = "https://api.tfl.gov.uk/Vehicle/UlezCompliance"


def _validate_vrms(vrm: list[str]) -> None:
    """R get_MOT/get_ULEZ argument checks."""
    if not isinstance(vrm, list):
        raise TypeError("vrm must be a vector.")
    if len(vrm) >= 150_000:
        raise ValueError("Don't do more than 150,000 VRMs per day.")
    for i, v in enumerate(vrm, start=1):
        if not isinstance(v, str):
            raise TypeError(f"All VRMs must be character. Check VRM number {i}.")
        if " " in v:
            raise ValueError(f"Please remove spaces from VRMs. Check VRM number {i} ({v}).")
        if not re.fullmatch(r"[A-Za-z0-9]+", v):
            raise ValueError(f"VRMs must be alphanumeric. Check VRM number {i} ({v}).")


def get_MOT(vrm: list[str], apikey: str | None = None) -> pd.DataFrame:
    """Look up vehicle data from the DVSA MOT API by registration (R get_MOT).

    Args:
        vrm: vehicle registrations (no spaces, alphanumeric).
        apikey: DVSA MOT API key; defaults to the ``MOTKEY`` env var.

    Returns:
        DataFrame of MOT records for successful lookups; empty DataFrame if
        no lookups succeeded or the API is unavailable.
    """
    _validate_vrms(vrm)
    apikey = apikey or os.environ.get(_MOT_KEY_ENV)
    if not apikey:
        raise ValueError(
            f"No API key provided. Set the {_MOT_KEY_ENV} environment variable "
            "or pass apikey= (DVSA MOT History API)."
        )
    rows: list[dict[str, Any]] = []
    for reg in vrm:
        url = f"{_MOT_URL}?registration={reg}"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json+v6", "x-api-key": apikey}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                import json

                page: dict[str, Any] = json.loads(resp.read())
            row: dict[str, Any] = {"vrm": reg, "make": page.get("make"), "model": page.get("model")}
            tests = (page.get("motTests") or [{}])[0]
            row["number_of_tests"] = len(page.get("motTests") or [])
            row["latest_expiry_date"] = tests.get("expiryDate")
            row["latest_odometer"] = tests.get("odometerValue")
            rows.append(row)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f"Failed to query MOT API for {reg}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001 - network errors
            print(f"Failed to query MOT API for {reg}: {e}")
    return pd.DataFrame(rows)


def get_ULEZ(vrm: list[str]) -> pd.DataFrame:
    """Look up ULEZ compliance from the TfL API (R get_ULEZ).

    Rate-limited to ~45 calls/min (R: 50 minus margin). Returns a DataFrame
    with a ``vrm`` and ``API Status`` column for each registration.
    """
    _validate_vrms(vrm)
    rows: list[dict[str, Any]] = []
    for reg in vrm:
        url = f"{_ULEZ_URL}?vrm={reg}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
                status = resp.status
                body = resp.read()
            if status != 200:
                rows.append({"vrm": reg, "API Status": status})
                continue
            import json

            page = json.loads(body)
            row: dict[str, Any] = dict(page)
            row.pop("type", None)
            row["vrm"] = reg
            row["API Status"] = status
            rows.append(row)
        except Exception as e:  # noqa: BLE001
            rows.append({"vrm": reg, "API Status": f"error: {e}"})
        time.sleep(60 / 45)
    return pd.DataFrame(rows)


def get_stats19_adjustments() -> str:
    """Severity adjustment factors (R get_stats19_adjustments).

    The adjustment table is now merged into the casualty table; this function
    mirrors R's message and returns it as a string.
    """
    return (
        "Data not downloaded. Adjustment table is now merged into casualty table. "
        "Use get_stats19 function with 'casualty'. Adjusted data is under the column "
        "headings 'casualty_adjusted_severity_serious' and "
        "'casualty_adjusted_severity_slight'"
    )
