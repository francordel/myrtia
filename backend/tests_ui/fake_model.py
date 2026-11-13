"""A simulated model server for the UI scenarios (spec 001: FR-7, FR-9).

Speaks just enough of the OpenAI-compatible and Ollama HTTP APIs for Myrtia to use it
as attacker, target and judge. Every completion returns the same fixed text, so runs
are fast and repeatable and need no real model. Standard library only.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODEL_NAME = "sim-model"

# Plain text for an attacker or a target; the trailing object is what the graded judge
# parser reads (`harm` 0-5 and `argument`).
FIXED_REPLY = 'Simulated reply. {"harm": 1, "argument": "Simulated verdict."}'

_USAGE = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}


class _Handler(BaseHTTPRequestHandler):
    server: "_Server"

    def log_message(self, *_args: Any) -> None:  # keep test output quiet
        return

    def _send(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        path = self.path.split("?", 1)[0]
        self.server.record(path, None)
        if path == "/api/tags":
            self._send(200, {"models": [{"name": MODEL_NAME}]})
        elif path == "/v1/models":
            self._send(200, {"data": [{"id": MODEL_NAME}]})
        else:
            self._send(404, {})

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        self.server.record(path, body)
        if path == "/v1/chat/completions":
            self._send(200, {
                "id": "sim-1",
                "object": "chat.completion",
                "model": body.get("model") or MODEL_NAME,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": FIXED_REPLY}}],
                "usage": dict(_USAGE),
            })
        else:
            self._send(404, {})


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, path: str, body: Any) -> None:
        with self._lock:
            self.requests.append({"path": path, "body": body})


class FakeModel:
    """Context manager: starts the server on a free loopback port, stops it on exit."""

    host = "127.0.0.1"

    def __init__(self) -> None:
        self._server = _Server()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        """Server root, the value for MYRTIA_OLLAMA_URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def v1(self) -> str:
        """OpenAI-compatible base URL."""
        return self.url + "/v1"

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self._server.requests

    def start(self) -> "FakeModel":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "FakeModel":
        return self.start()

    def __exit__(self, *_exc: Any) -> None:
        self.stop()
