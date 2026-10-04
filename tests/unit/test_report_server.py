from __future__ import annotations

import os
import socket
import threading
from collections.abc import Iterator
from contextlib import closing
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

import pytest

from retail_pipeline.report_server import MAX_REPORT_BYTES, ReportHandler, open_report


@pytest.fixture
def report_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "report.html").write_bytes(b"<!doctype html><title>Fechamento</title>")
    (root / "explain.json").write_bytes(b'{"private": "origin details"}')
    (root / ".env").write_bytes(b"PRIVATE=fixture")
    (tmp_path / "private.html").write_bytes(b"private outside report directory")
    return root


@pytest.fixture
def server(report_root: Path) -> Iterator[HTTPServer]:
    class Handler(ReportHandler):
        root = report_root

    with HTTPServer(("127.0.0.1", 0), Handler) as instance:
        worker = threading.Thread(target=instance.serve_forever, daemon=True)
        worker.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            worker.join(timeout=5)


def request(server: HTTPServer, path: str, *, method: str = "GET", host: str | None = None):
    with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as connection:
        connection.request(method, path, headers={"Host": host} if host else {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()


@pytest.mark.parametrize("path", ["/report.html", "/", "/report.html?inspection=1"])
def test_only_report_html_is_served_with_browser_protections(server: HTTPServer, path: str):
    status, headers, payload = request(server, path)
    assert status == 200
    assert payload == b"<!doctype html><title>Fechamento</title>"
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"
    assert "script-src 'sha256-" in headers["Content-Security-Policy"]
    assert "connect-src 'none'" in headers["Content-Security-Policy"]
    assert "Python" not in headers["Server"]


@pytest.mark.parametrize(
    "path",
    [
        "/explain.json",
        "/.env",
        "/../private.html",
        "/%2e%2e/private.html",
        "/%2e%2e%5cprivate.html",
        "/subdirectory/report.html",
        "/.hidden.html",
        "/report.html:private",
        "/missing.html",
        "/%00report.html",
    ],
)
def test_private_artifacts_directories_and_traversal_are_unavailable(
    server: HTTPServer, report_root: Path, path: str
):
    status, _, payload = request(server, path)
    assert status == 404
    assert str(report_root).encode() not in payload
    assert b"origin details" not in payload
    assert b"private outside" not in payload
    assert b"PRIVATE=fixture" not in payload


@pytest.mark.parametrize("host", ["attacker.example", "localhost.attacker.example", "127.0.0.1@x"])
def test_foreign_hosts_cannot_read_reports_by_dns_rebinding(server: HTTPServer, host: str):
    status, _, payload = request(server, "/report.html", host=host)
    assert status == 403
    assert b"Fechamento" not in payload


def test_head_and_unsupported_methods_do_not_modify_files(server: HTTPServer, report_root: Path):
    expected = (report_root / "report.html").read_bytes()
    status, headers, payload = request(server, "/report.html", method="HEAD")
    assert status == 200 and payload == b""
    assert int(headers["Content-Length"]) == len(expected)
    for method in ("POST", "PUT", "DELETE"):
        status, _, _ = request(server, "/report.html", method=method)
        assert status == 501
    assert (report_root / "report.html").read_bytes() == expected


def test_symlink_cannot_expose_outside_html(report_root: Path):
    link = report_root / "linked.html"
    try:
        link.symlink_to(report_root.parent / "private.html")
    except OSError:
        pytest.skip("Criação de symlink indisponível neste host; CI Linux cobre o caso.")
    with pytest.raises(FileNotFoundError):
        open_report(report_root, "/linked.html")


def test_opened_file_identity_rejects_replacement_race(report_root: Path, monkeypatch):
    original_open = os.open

    def replace_then_open(path, flags):
        target = report_root / "report.html"
        target.rename(report_root / "old.html")
        target.write_bytes(b"replacement")
        return original_open(path, flags)

    monkeypatch.setattr(os, "open", replace_then_open)
    with pytest.raises(FileNotFoundError):
        open_report(report_root, "/report.html")


def test_oversized_report_is_refused_before_response(report_root: Path, monkeypatch):
    from retail_pipeline import report_server

    monkeypatch.setattr(report_server, "MAX_REPORT_BYTES", 1)
    assert MAX_REPORT_BYTES == 64 * 1024 * 1024
    with pytest.raises(FileNotFoundError):
        open_report(report_root, "/report.html")


def test_file_growth_does_not_send_bytes_beyond_content_length(
    server: HTTPServer, report_root: Path, monkeypatch
):
    expected = (report_root / "report.html").read_bytes()
    original_end_headers = ReportHandler.end_headers

    def append_after_size_is_declared(handler):
        with (report_root / "report.html").open("ab") as report:
            report.write(b"private appended bytes")
        original_end_headers(handler)

    monkeypatch.setattr(ReportHandler, "end_headers", append_after_size_is_declared)
    with closing(socket.create_connection(("127.0.0.1", server.server_port), timeout=5)) as stream:
        stream.sendall(b"GET /report.html HTTP/1.0\r\nHost: localhost\r\n\r\n")
        received = bytearray()
        while block := stream.recv(65536):
            received.extend(block)
    header, payload = received.split(b"\r\n\r\n", 1)
    assert b"200 OK" in header
    assert f"Content-Length: {len(expected)}".encode() in header
    assert payload == expected
