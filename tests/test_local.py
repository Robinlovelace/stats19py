"""Pre-downloaded data: file resolution across DfT naming vintages, offline mode."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import stats19
from stats19 import core, local

P = "dft-road-casualty-statistics-"

CAS_HEADER = (
    "collision_index,collision_year,collision_ref_no,casualty_reference,casualty_severity\n"
)
OLD_CAS_HEADER = (
    "﻿accident_index,accident_year,accident_reference,casualty_reference,casualty_severity\n"
)


def _write(d: Path, name: str, text: str) -> Path:
    path = d / f"{P}{name}.csv"
    path.write_text(text, encoding="utf-8")
    return path


def _history(d: Path) -> Path:
    rows = "".join(
        f"{y}01X{i},{y},01X{i},1,{1 + i % 3}\n" for y in (2018, 2019, 2024) for i in (1, 2)
    )
    return _write(d, "casualty-1979-latest-published-year", CAS_HEADER + rows)


def test_inventory_recognises_every_vintage(tmp_path: Path) -> None:
    for name in [
        "accident-2019",
        "casualty-1979-2021",
        "collision-1979-latest-published-year",
        "accident-last-5-years",
        "casualty-2024",
        "casualties-adjustment-last-5-years",
    ]:
        _write(tmp_path, name, "x\n")
    found = {f.name: f for f in local.inventory(str(tmp_path))}
    assert found[f"{P}accident-2019.csv"].table == "collision"
    assert found[f"{P}casualty-1979-2021.csv"].covers(2021)
    assert not found[f"{P}casualty-1979-2021.csv"].covers(2022)
    assert found[f"{P}casualty-2024.csv"].in_manifest
    assert not found[f"{P}accident-2019.csv"].in_manifest
    assert f"{P}casualties-adjustment-last-5-years.csv" not in found


def test_manifest_mismatches(tmp_path: Path) -> None:
    _write(tmp_path, "accident-2019", "x\n")
    _write(tmp_path, "casualty-2024", "x\n")
    mm = local.manifest_mismatches(str(tmp_path))
    assert mm["not_in_manifest"] == [f"{P}accident-2019.csv"]
    assert f"{P}casualty-2024.csv" not in mm["manifest_not_on_disk"]
    assert len(mm["manifest_not_on_disk"]) == 25


def test_resolve_prefers_history_file_for_old_years(tmp_path: Path) -> None:
    _history(tmp_path)
    _write(tmp_path, "casualty-2019", OLD_CAS_HEADER)
    res = local.resolve("casualty", [2019], str(tmp_path))
    assert [f.span for f in res.files] == ["1979-latest-published-year"]
    assert res.year_filter == [2019]
    assert res.missing == []


def test_resolve_falls_back_to_legacy_per_year_files(tmp_path: Path) -> None:
    _write(tmp_path, "casualty-2019", OLD_CAS_HEADER)
    _write(tmp_path, "casualty-2024", CAS_HEADER)
    res = local.resolve("casualty", [2019, 2024], str(tmp_path))
    assert [f.span for f in res.files] == ["2019", "2024"]
    assert res.missing == []
    assert any("older DfT vintage" in n for n in res.notes)


def test_resolve_reports_missing_manifest_names(tmp_path: Path) -> None:
    _write(tmp_path, "casualty-2017", OLD_CAS_HEADER)
    res = local.resolve("casualty", [2018], str(tmp_path))
    assert res.files == []
    assert res.missing == [f"{P}casualty-1979-latest-published-year.csv"]


def test_year_five_means_last_five_years() -> None:
    # R returns the 1979 history for the number 5. The port does not.
    assert core.find_file_name(5, "collision") == [f"{P}collision-last-5-years.csv"]


def test_year_slice_is_lossless(tmp_path: Path) -> None:
    path = _history(tmp_path)
    full = core._read_csv(str(path))
    with local.year_slice(str(path), [2019]) as sliced:
        part = core._read_csv(sliced)
    expected = full[full["collision_year"] == 2019].reset_index(drop=True)
    pd.testing.assert_frame_equal(part, expected)
    assert not Path(sliced).exists()


def test_read_filters_history_file_by_year(tmp_path: Path) -> None:
    _history(tmp_path)
    df = stats19.read_casualties(2019, data_dir=str(tmp_path), format=False)
    assert df is not None and len(df) == 2
    assert set(df["collision_year"]) == {2019}


def test_read_aligns_mixed_vintages(tmp_path: Path) -> None:
    _write(tmp_path, "casualty-2019", OLD_CAS_HEADER + "2019X1,2019,X1,1,2\n")
    _write(tmp_path, "casualty-2024", CAS_HEADER + "2024X1,2024,X1,1,3\n")
    df = stats19.read_casualties([2019, 2024], data_dir=str(tmp_path), format=False)
    assert df is not None and len(df) == 2
    assert {"collision_index", "collision_year"} <= set(df.columns)
    assert not any(c.startswith("accident") for c in df.columns)


def test_dl_skips_when_local_files_cover_request(tmp_path: Path) -> None:
    # The autouse guard in conftest fails the test on any download attempt.
    _history(tmp_path)
    path = stats19.dl_stats19(2019, type="casualty", data_dir=str(tmp_path), silent=True)
    assert path is not None and path.endswith("casualty-1979-latest-published-year.csv")


def test_offline_raises_instead_of_downloading(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(local.OFFLINE_ENV, "1")
    _write(tmp_path, "vehicle-2017", "x\n")
    with pytest.raises(local.OfflineError, match="vehicle-1979-latest-published-year"):
        stats19.dl_stats19(2019, type="vehicle", data_dir=str(tmp_path), silent=True)


def test_offline_get_uses_local_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(local.OFFLINE_ENV, "1")
    _history(tmp_path)
    df = stats19.get_casualties(2024, data_dir=str(tmp_path), silent=True, format=False)
    assert df is not None and len(df) == 2
