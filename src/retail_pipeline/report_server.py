"""Servidor local de relatórios; os demais artefatos são lidos pelo operador no disco."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit

from retail_pipeline.report_view import SCRIPT

MAX_REPORT_BYTES = 64 * 1024 * 1024
REPORT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.html")
LOCAL_HOST = re.compile(r"(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?", re.IGNORECASE)
SCRIPT_HASH = b64encode(hashlib.sha256(SCRIPT.encode("utf-8")).digest()).decode("ascii")
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    f"script-src 'sha256-{SCRIPT_HASH}'; "
    "style-src 'unsafe-inline'; font-src data:; img-src data:; "
    "connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def open_report(root: Path, request_path: str) -> BinaryIO:
    """Abre somente HTML regular na raiz, sem seguir links ou refletir caminhos em erros."""
    path = unquote(urlsplit(request_path).path, errors="strict")
    name = "report.html" if path == "/" else path.removeprefix("/")
    if REPORT_NAME.fullmatch(name) is None or root.is_symlink():
        raise FileNotFoundError
    candidate = root / name
    before = candidate.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise FileNotFoundError
    descriptor = os.open(
        candidate,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size > MAX_REPORT_BYTES
        ):
            raise FileNotFoundError
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


class ReportHandler(BaseHTTPRequestHandler):
    server_version = "VarejoReport"
    sys_version = ""
    root = Path("artifacts")

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _report(self, *, body: bool) -> None:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or LOCAL_HOST.fullmatch(hosts[0]) is None:
            self.send_error(403)
            return
        try:
            report = open_report(self.root, self.path)
        except (OSError, UnicodeError, ValueError):
            self.send_error(404)
            return
        with report:
            remaining = os.fstat(report.fileno()).st_size
            if remaining > MAX_REPORT_BYTES:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(remaining))
            self.end_headers()
            if body:
                # Uma exportação pode crescer durante a resposta: preservar o teto
                # e o tamanho declarado, sem enviar os bytes acrescentados depois.
                while remaining:
                    block = report.read(min(64 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)

    def do_GET(self) -> None:
        self._report(body=True)

    def do_HEAD(self) -> None:
        self._report(body=False)

    def log_message(self, format: str, *args: object) -> None:
        # A URL pode carregar parâmetros sensíveis; não registrar seu conteúdo.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Servir relatórios HTML locais")
    parser.add_argument("port", type=int, nargs="?", default=3103)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--directory", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    if args.directory.is_symlink() or not args.directory.is_dir():
        parser.error("--directory exige uma pasta existente sem link simbólico.")
    ReportHandler.root = args.directory.resolve(strict=True)
    with HTTPServer((args.bind, args.port), ReportHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
