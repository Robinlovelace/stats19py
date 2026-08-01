"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def data_dir_2024() -> Path:
    """Real DfT data dir (2024+2025 CSVs) committed locally, gitignored."""
    d = Path(__file__).resolve().parents[1] / "data"
    if not (d / "dft-road-casualty-statistics-collision-2024.csv").exists():
        pytest.skip(
            "real DfT data not downloaded (run: uv run python -c 'from stats19 import dl_stats19; dl_stats19(2024, data_dir=\"data\")')"
        )
    return d
