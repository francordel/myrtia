"""A stand-in for the dashboard server in the UI scenarios (spec 008: FR-20 to FR-22).

Answers the health address the console checks and serves a page at the dashboard's
address. `up` switches it between "running" and "not running". Standard library only.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PAGE_TITLE = "Simulated dashboard"


class _Handler(BaseHTTPRequestHandler):
    server: "_Server"

    def log_message(self, *_args: Any) -> None:  # keep test output quiet
        return

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            if self.server.up:
                self._send(200, json.dumps({"database": "ok"}).encode(), "application/json")
            else:
                self._send(503, b"{}", "application/json")
        elif path.startswith("/d/"):
            html = f"<!doctype html><title>{PAGE_TITLE}</title><h1>{PAGE_TITLE}</h1>"
            self._send(200, html.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"{}", "application/json")


    def do_POST(self) -> None:  # noqa: N802 - http.server API
        # Accepts (and drops) the traces the instance exports, so nothing is retried.
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._send(200, b"{}", "application/json")


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    up = True


class FakeGrafana:
    """Context manager: a dashboard server on a free local port."""

    def __init__(self) -> None:
        self._server = _Server(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def up(self) -> bool:
        return self._server.up

    @up.setter
    def up(self, value: bool) -> None:
        self._server.up = value

    def __enter__(self) -> "FakeGrafana":
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
