"""Tests for downloading STATS19 data (Slice 2).

Uses a local HTTP server stub so tests are deterministic and offline.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from stats19 import download, files


class StubHandler(BaseHTTPRequestHandler):
    """Serves small fake CSV files for any requested path."""

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        body = (
            b"accident_index,accident_year,accident_severity\n"
            b"202401000001,2024,2\n"
            b"202401000002,2024,1\n"
        )
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002, N803
        pass


@pytest.fixture(scope="module")
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_dl_stats19_downloads_file(stub_server: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(download, "get_url", lambda f: f"{stub_server}/{f}")
    result = download.dl_stats19(
        year=2024,
        data_dir=str(tmp_path),
        silent=True,
        timeout=30,
    )
    expected = tmp_path / "dft-road-casualty-statistics-collision-2024.csv"
    assert result == str(expected)
    assert expected.exists()
    assert "accident_index" in expected.read_text()


def test_dl_stats19_skips_existing(stub_server: str, tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(download, "get_url", lambda f: f"{stub_server}/{f}")
    target = tmp_path / "dft-road-casualty-statistics-collision-2024.csv"
    target.write_text("already there")
    download.dl_stats19(year=2024, data_dir=str(tmp_path), silent=False, timeout=30)
    captured = capsys.readouterr()
    assert "already exists" in captured.out
    assert target.read_text() == "already there"


def test_dl_stats19_creates_data_dir(stub_server: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(download, "get_url", lambda f: f"{stub_server}/{f}")
    target_dir = tmp_path / "nested" / "data"
    download.dl_stats19(year=2024, data_dir=str(target_dir), silent=True, timeout=30)
    assert (target_dir / "dft-road-casualty-statistics-collision-2024.csv").exists()


def test_dl_stats19_multiple_files(stub_server: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(download, "get_url", lambda f: f"{stub_server}/{f}")
    download.dl_stats19(year=2024, type="all", data_dir=str(tmp_path), silent=True, timeout=30)
    names = files.find_file_name(2024)
    for n in names:
        assert (tmp_path / n).exists()
