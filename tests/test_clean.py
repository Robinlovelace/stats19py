"""Slice 7: cleaning functions + env-var data dir + API lookups."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from stats19 import clean, get_stats19_adjustments, set_data_directory
from stats19.api import _validate_vrms, get_MOT, get_ULEZ
from stats19.core import get_data_directory


def test_extract_make_multiword() -> None:
    s = pd.Series(["FORD FIESTA", "LAND ROVER DISCOVERY", "ALFA ROMEO GIULIA"])
    assert clean.extract_make_stats19(s).tolist() == ["FORD", "LAND ROVER", "ALFA ROMEO"]


def test_extract_make_removes_parentheses() -> None:
    s = pd.Series(["FORD (NEW) FIESTA", "BMW 3 SERIES"])
    assert clean.extract_make_stats19(s).tolist() == ["FORD", "BMW"]


def test_clean_make_title_case_and_merges() -> None:
    s = pd.Series(["VW GOLF", "Mercedez C CLASS", "FORD FIESTA", "RANGE ROVER SPORT"])
    out = clean.clean_make(s).tolist()
    assert out == ["Volkswagen", "Mercedes", "Ford", "Land Rover"]


def test_clean_make_na_values() -> None:
    s = pd.Series(["-1", "Other", "FORD"])
    out = clean.clean_make(s).tolist()
    assert pd.isna(out[0]) and pd.isna(out[1])
    assert out[2] == "Ford"


def test_clean_make_uppercase_brands() -> None:
    s = pd.Series(["BMW 320", "MINI COOPER", "DAF TRUCKS LF"])
    assert clean.clean_make(s).tolist() == ["BMW", "MINI", "DAF"]


def test_clean_make_no_extract() -> None:
    s = pd.Series(["FORD", "VW"])
    out = clean.clean_make(s, extract_make=False).tolist()
    # R: "VW" -> "Volkswagen" (regex Volksw|VW catches bare VW too)
    assert out == ["Ford", "Volkswagen"]


def test_clean_model_extracts_remainder() -> None:
    s = pd.Series(["FORD FIESTA", "BMW 3 SERIES", "LAND ROVER DISCOVERY"])
    out = clean.clean_model(s).tolist()
    assert out == ["Fiesta", "3 Series", "Discovery"]


def test_clean_model_invalid_to_na() -> None:
    s = pd.Series(["FORD MISSING", "BMW AND MODEL REDACTED"])
    out = clean.clean_model(s).tolist()
    assert pd.isna(out[0]) and pd.isna(out[1])


def test_clean_make_model_combines() -> None:
    s = pd.Series(["FORD FIESTA", "BMW 3 SERIES"])
    assert clean.clean_make_model(s).tolist() == ["Ford Fiesta", "BMW 3 Series"]


def test_str_to_title_matches_r_icu_rules() -> None:
    """R str_to_title: first letter of word uppercased, rest lowercased,
    digits don't start new words (verified against stringr::str_to_title)."""
    cases = {
        "500X": "500x",
        "A1B2": "A1b2",
        "X500": "X500",
        "3 SERIES": "3 Series",
        "C220": "C220",
        "GLC300": "Glc300",
        "1.0X": "1.0x",
        "5X": "5x",
        "X5Y": "X5y",
    }
    for raw, expected in cases.items():
        assert clean._str_to_title(raw) == expected, f"{raw!r} -> {expected!r}"


def test_get_stats19_adjustments_message() -> None:
    msg = get_stats19_adjustments()
    assert "casualty_adjusted_severity_serious" in msg


def test_data_directory_env_var(monkeypatch, tmp_path) -> None:
    """Data location is controlled by STATS19_DOWNLOAD_DIRECTORY env var."""
    old = os.environ.get("STATS19_DOWNLOAD_DIRECTORY")
    try:
        monkeypatch.delenv("STATS19_DOWNLOAD_DIRECTORY", raising=False)
        assert get_data_directory() == os.path.join(os.getcwd(), "data")
        set_data_directory(str(tmp_path))
        assert get_data_directory() == str(tmp_path)
    finally:
        # restore exactly (monkeypatch.undo() alone re-applies mid-test value)
        if old is None:
            os.environ.pop("STATS19_DOWNLOAD_DIRECTORY", None)
        else:
            os.environ["STATS19_DOWNLOAD_DIRECTORY"] = old


def test_validate_vrms_errors() -> None:
    with pytest.raises(TypeError):
        _validate_vrms("1RAC")  # type: ignore[arg-type]  # not a list
    with pytest.raises(ValueError, match="spaces"):
        _validate_vrms(["1 RAC"])
    with pytest.raises(ValueError, match="alphanumeric"):
        _validate_vrms(["1RAC!"])
    with pytest.raises(ValueError, match="150,000"):
        _validate_vrms(["1"] * 150_000)


def test_get_MOT_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("MOTKEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        get_MOT(["1RAC"])


def test_get_ULEZ_offline_graceful(monkeypatch) -> None:
    """Without network the TfL API call fails but returns a row (graceful)."""

    def fake_urlopen(*args, **kwargs):
        raise OSError("simulated network failure")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    df = get_ULEZ(["1RAC"])
    assert isinstance(df, pd.DataFrame)
    assert "vrm" in df.columns or "API Status" in df.columns
