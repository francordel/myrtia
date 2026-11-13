"""A private Myrtia instance for the UI scenarios (spec 001: FR-2, FR-3, FR-4, FR-13).

Starts the real application as a subprocess on a free loopback port, with a temporary
database and data folder, pointed at the simulated model. Nothing it does can reach the
operator's own run history, settings or keys.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fake_model import MODEL_NAME

_BACKEND = Path(__file__).resolve().parent.parent

# Variables that must never reach the instance: the access token (the instance is not
# gated) and any provider key the developer has exported.
_DROPPED = ("MYRTIA_TOKEN", "MYRTIA_ALLOW_ORIGINS", "MYRTIA_COUNCIL_PHASE2_FILE")
_KEY_SUFFIXES = ("_API_KEY", "_TOKEN")


class AppStartError(RuntimeError):
    """The application instance did not start; the message includes its output."""


def free_port() -> int:
    """A loopback port that is free right now."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def app_env(base: Mapping[str, str], *, data_dir: os.PathLike[str] | str,
            model_url: str) -> dict[str, str]:
    """Environment for the instance: private data, simulated model, no secrets."""
    env = {k: v for k, v in base.items()
           if k not in _DROPPED and not k.endswith(_KEY_SUFFIXES)}
    data = Path(data_dir)
    env["MYRTIA_DB"] = str(data / "myrtia.db")
    env["MYRTIA_GOAL_DATA_DIR"] = str(data / "goals")
    env["MYRTIA_OLLAMA_URL"] = model_url
    env["MYRTIA_DEFAULT_MODEL"] = MODEL_NAME
    return env


class AppInstance:
    """Context manager around one application subprocess."""

    def __init__(self, *, model_url: str, command: Sequence[str] | None = None,
                 ready_timeout: float = 60.0) -> None:
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}/"
        self.data_dir = tempfile.mkdtemp(prefix="myrtia-ui-")
        self._model_url = model_url
        self._command = list(command) if command else [
            sys.executable, "-m", "uvicorn", "myrtia.api.app:app",
            "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "warning"]
        self._ready_timeout = ready_timeout
        self._log_path = os.path.join(self.data_dir, "app.log")
        self._log: Any = None
        self.process: subprocess.Popen[bytes] | None = None

    def output(self) -> str:
        """Everything the instance has printed so far."""
        try:
            return Path(self._log_path).read_text(errors="replace")
        except OSError:
            return ""

    def start(self) -> "AppInstance":
        env = app_env(os.environ, data_dir=self.data_dir, model_url=self._model_url)
        self._log = open(self._log_path, "wb")  # noqa: SIM115 - closed in stop()
        self.process = subprocess.Popen(  # noqa: S603 - fixed, local command
            self._command, cwd=str(_BACKEND), env=env,
            stdout=self._log, stderr=subprocess.STDOUT)
        try:
            self._wait_ready()
        except AppStartError:
            self.stop()
            raise
        return self

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self._ready_timeout
        while time.monotonic() < deadline:
            assert self.process is not None
            code = self.process.poll()
            if code is not None:
                raise AppStartError(
                    f"The application exited with code {code} before it was ready.\n"
                    f"--- startup output ---\n{self.output()}")
            try:
                with urllib.request.urlopen(self.url, timeout=1) as r:  # noqa: S310
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        raise AppStartError(
            f"The application did not become ready within {self._ready_timeout:g}s "
            f"at {self.url}\n--- startup output ---\n{self.output()}")

    def stop(self) -> None:
        proc, self.process = self.process, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        if self._log is not None:
            self._log.close()
            self._log = None
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def __enter__(self) -> "AppInstance":
        return self.start()

    def __exit__(self, *_exc: Any) -> None:
        self.stop()
