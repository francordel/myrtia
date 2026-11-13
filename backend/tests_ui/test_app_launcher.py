"""Unit tests for the private application instance (spec 001: FR-2, FR-3, FR-13)."""
from __future__ import annotations

import os
import socket
import sys
import urllib.request

import pytest

from app_launcher import AppInstance, AppStartError, app_env, free_port
from fake_model import FakeModel


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_free_port_is_usable() -> None:
    port = free_port()
    assert 1024 < port < 65536
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))  # nothing else holds it


def test_app_env_points_at_private_data_and_the_simulated_model(tmp_path) -> None:
    base = {"PATH": "/usr/bin", "MYRTIA_TOKEN": "secret", "MYRTIA_DB": "/real/myrtia.db",
            "OPENAI_API_KEY": "sk-real"}
    env = app_env(base, data_dir=tmp_path, model_url="http://127.0.0.1:9")
    assert env["MYRTIA_DB"] == str(tmp_path / "myrtia.db")
    assert env["MYRTIA_GOAL_DATA_DIR"] == str(tmp_path / "goals")
    assert env["MYRTIA_OLLAMA_URL"] == "http://127.0.0.1:9"
    assert env["MYRTIA_DEFAULT_MODEL"] == "sim-model"
    assert "MYRTIA_TOKEN" not in env          # the instance is not gated
    assert "OPENAI_API_KEY" not in env        # no real key reaches the instance
    assert env["PATH"] == "/usr/bin"
    assert base["MYRTIA_DB"] == "/real/myrtia.db"  # the caller's env is untouched


def test_instance_serves_the_ui_and_cleans_up() -> None:
    with FakeModel() as model, AppInstance(model_url=model.url) as app:
        port, data_dir = app.port, app.data_dir
        with urllib.request.urlopen(app.url, timeout=5) as r:  # noqa: S310 - loopback
            assert r.status == 200
            assert b"MYRTIA" in r.read()
        assert os.path.isdir(data_dir)
    assert not _port_open(port)               # process stopped
    assert not os.path.exists(data_dir)       # temporary data removed


def test_instance_uses_its_own_database() -> None:
    with FakeModel() as model, AppInstance(model_url=model.url) as app:
        assert os.path.isfile(os.path.join(app.data_dir, "myrtia.db"))


def test_start_error_carries_the_startup_output() -> None:
    boom = [sys.executable, "-c", "print('boom-from-startup'); raise SystemExit(3)"]
    app = AppInstance(model_url="http://127.0.0.1:9", command=boom, ready_timeout=10)
    with pytest.raises(AppStartError) as exc:
        app.start()
    assert "boom-from-startup" in str(exc.value)
    assert not os.path.exists(app.data_dir)   # cleaned up even though start failed


def test_start_error_when_never_ready() -> None:
    idle = [sys.executable, "-c", "import time; print('idle-app'); time.sleep(30)"]
    app = AppInstance(model_url="http://127.0.0.1:9", command=idle, ready_timeout=1.5)
    with pytest.raises(AppStartError) as exc:
        app.start()
    assert "did not become ready" in str(exc.value)
    assert app.process is None or app.process.poll() is not None  # no process left behind
