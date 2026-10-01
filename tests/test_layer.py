"""Casualty layer on small synthetic files, across DfT naming vintages."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

import stats19
from stats19 import local

P = "dft-road-casualty-statistics-"

COL = (
    "collision_index,collision_year,date,time,longitude,latitude,location_easting_osgr,"
    "location_northing_osgr,local_authority_ons_district,local_authority_highway,"
    "local_authority_highway_current,collision_severity,number_of_casualties\n"
)
CAS = (
    "collision_index,collision_year,vehicle_reference,casualty_reference,casualty_severity,"
    "casualty_type,casualty_adjusted_severity_serious\n"
)
OLD_COL = (
    "﻿accident_index,accident_year,date,time,longitude,latitude,location_easting_osgr,"
    "location_northing_osgr,local_authority_ons_district,local_authority_highway,"
    "accident_severity,number_of_casualties\n"
)
OLD_CAS = (
    "﻿accident_index,accident_year,vehicle_reference,casualty_reference,casualty_severity,"
    "casualty_type\n"
)


def _write(d: Path, name: str, text: str) -> None:
    (d / f"{P}{name}.csv").write_text(text, encoding="utf-8")


@pytest.fixture
def lake(tmp_path: Path) -> Path:
    _write(
        tmp_path,
        "collision-2024",
        COL
        + "2024A,2024,01/03/2024,08:00,-1.55,53.80,430000,433000,"
        + "E08000035,E08000035,E08000035,2,2\n"
        + "2024B,2024,02/03/2024,09:00,-1.10,53.95,460000,450000,"
        + "E06000014,E06000014,E06000014,3,1\n"
        + "2024C,2024,03/03/2024,10:00,-1,-1,-1,-1,E08000035,E08000035,E08000035,1,1\n",
    )
    _write(
        tmp_path,
        "casualty-2024",
        CAS
        + "2024A,2024,1,1,2,1,1\n"
        + "2024A,2024,2,2,3,0,0.25\n"
        + "2024B,2024,1,1,3,9,0.1\n"
        + "2024C,2024,1,1,1,33,0\n",
    )
    # 2019 only exists under the old accident naming.
    _write(
        tmp_path,
        "accident-2019",
        OLD_COL + "2019A,2019,05/06/2019,12:00,-1.50,53.79,431000,432000,E08000035,E08000035,3,1\n",
    )
    _write(tmp_path, "casualty-2019", OLD_CAS + "2019A,2019,1,1,3,9\n")
    return tmp_path


def _rows(path: str) -> list[tuple]:
    return duckdb.sql(f"SELECT * FROM '{path}'").fetchall()


def test_layer_counts_and_modes(lake: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    summary = stats19.casualty_layer(2024, str(out), authorities=["E08000035"], data_dir=str(lake))
    con = duckdb.connect()
    col = con.sql(f"SELECT * FROM '{out}/collisions.parquet' ORDER BY collision_index").df()
    assert list(col["collision_index"]) == ["2024A", "2024C"]
    a = col.iloc[0]
    assert (a["n_casualties"], a["n_serious"], a["n_slight"], a["n_ksi"]) == (2, 1, 1, 1)
    assert a["ksi_adjusted"] == pytest.approx(1.25)
    assert (a["n_cyclist"], a["n_pedestrian"]) == (1, 1)
    c = col.iloc[1]
    assert (c["n_fatal"], c["n_e_scooter"], c["ksi_adjusted"]) == (1, 1, 1.0)
    assert str(a["date"])[:10] == "2024-03-01"
    cas = con.sql(f"SELECT mode FROM '{out}/casualties.parquet' ORDER BY mode").fetchall()
    assert [m for (m,) in cas] == ["cyclist", "e_scooter", "pedestrian"]
    assert summary["rows_by_year"][0]["collisions_without_coordinates"] == 1
    assert json.loads((out / "casualty_layer.json").read_text())["filters"]["years"] == [2024]


def test_layer_bbox_in_both_crs(lake: Path, tmp_path: Path) -> None:
    out1, out2 = tmp_path / "wgs", tmp_path / "bng"
    stats19.casualty_layer(2024, str(out1), bbox=(-1.6, 53.7, -1.4, 53.9), data_dir=str(lake))
    stats19.casualty_layer(
        2024,
        str(out2),
        bbox=(425000, 425000, 435000, 440000),
        bbox_crs="EPSG:27700",
        data_dir=str(lake),
    )
    for out in (out1, out2):
        ids = [r[0] for r in _rows(f"{out}/collisions.parquet")]
        assert ids == ["2024A"]


def test_layer_mixes_vintages(lake: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    summary = stats19.casualty_layer(
        [2019, 2024], str(out), authorities=["E08000035"], data_dir=str(lake)
    )
    years = [r["year"] for r in summary["rows_by_year"]]
    assert years == [2019, 2024]
    assert any("older DfT vintage" in n for n in summary["notes"])
    n = duckdb.sql(f"SELECT count(*) FROM '{out}/casualties.parquet'").fetchone()
    assert n == (4,)


def test_layer_never_downloads(lake: Path, tmp_path: Path) -> None:
    with pytest.raises(local.OfflineError, match="never downloads"):
        stats19.casualty_layer(2018, str(tmp_path / "out"), data_dir=str(lake))


def test_cli(lake: Path, tmp_path: Path, capsys) -> None:
    stats19.main(
        [
            "casualties",
            "--years",
            "2024",
            "--authority",
            "E08000035",
            "--out",
            str(tmp_path / "cli"),
            "--data-dir",
            str(lake),
        ]
    )
    assert "2024: 2 collisions, 3 casualties, 2 KSI" in capsys.readouterr().out
