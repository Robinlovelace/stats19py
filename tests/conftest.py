"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def data_dir_2024() -> Path:
    """Real DfT data dir (2024+2025 CSVs): ./data, else STATS19_DOWNLOAD_DIRECTORY."""
    d = Path(__file__).resolve().parents[1] / "data"
    env = os.environ.get("STATS19_DOWNLOAD_DIRECTORY")
    if not (d / "dft-road-casualty-statistics-collision-2024.csv").exists() and env:
        d = Path(env)
    if not (d / "dft-road-casualty-statistics-collision-2024.csv").exists():
        pytest.skip(
            "real DfT data not downloaded (run: uv run python -c 'from stats19 import dl_stats19; dl_stats19(2024, data_dir=\"data\")')"
        )
    return d


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """Fail any test that tries to reach a host other than the local stub server.

    The real-data tests may point at a large pre-downloaded directory, so a
    stray download would be slow and would write into that directory.
    """
    import urllib.request

    real_urlopen = urllib.request.urlopen

    def guarded(url, *args, **kwargs):
        target = url if isinstance(url, str) else url.full_url
        if not target.startswith(("http://127.0.0.1", "http://localhost")):
            raise AssertionError(f"test attempted a download: {target}")
        return real_urlopen(url, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", guarded)
