"""Durable persistence (SQLite, stdlib only).

Runs and their event backlogs are written through to a local SQLite file so that
history, statistics and live-replay survive a backend restart. Secrets are redacted
before anything is written to disk.

The DB path is `$MYRTIA_DB` or `<repo>/.data/myrtia.db`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

_DEFAULT = Path(__file__).resolve().parents[3] / ".data" / "myrtia.db"
_PATH = Path(os.getenv("MYRTIA_DB", str(_DEFAULT)))
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_PATH), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS runs("
            "id TEXT PRIMARY KEY, created_at REAL, status TEXT, error TEXT,"
            "spec_json TEXT, results_json TEXT)"
        )
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS events("
            "run_id TEXT, seq INTEGER, ts REAL, type TEXT, payload_json TEXT, id TEXT,"
            "PRIMARY KEY(run_id, seq))"
        )
        _conn.commit()
    return _conn


def save_run(run_id: str, created_at: float, status: str, error: str | None,
             spec: dict[str, Any], results: list[dict]) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO runs(id,created_at,status,error,spec_json,results_json) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "status=excluded.status, error=excluded.error, results_json=excluded.results_json",
            (run_id, created_at, status, error,
             json.dumps(spec, ensure_ascii=False), json.dumps(results, ensure_ascii=False)),
        )
        c.commit()


def load_runs() -> list[dict[str, Any]]:
    c = _connect()
    rows = c.execute(
        "SELECT id,created_at,status,error,spec_json,results_json FROM runs "
        "ORDER BY created_at"
    ).fetchall()
    out = []
    for rid, created, status, error, spec_json, results_json in rows:
        out.append({
            "id": rid, "created_at": created, "status": status, "error": error,
            "spec": json.loads(spec_json) if spec_json else {},
            "results": json.loads(results_json) if results_json else [],
        })
    return out


def append_event(run_id: str, seq: int, ts: float, type_: str,
                 payload: dict[str, Any], ev_id: str) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "INSERT OR IGNORE INTO events(run_id,seq,ts,type,payload_json,id) "
            "VALUES(?,?,?,?,?,?)",
            (run_id, seq, ts, type_, json.dumps(payload, ensure_ascii=False), ev_id),
        )
        c.commit()


def load_events() -> dict[str, list[dict[str, Any]]]:
    c = _connect()
    rows = c.execute(
        "SELECT run_id,seq,ts,type,payload_json,id FROM events ORDER BY run_id,seq"
    ).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for run_id, seq, ts, type_, payload_json, ev_id in rows:
        out.setdefault(run_id, []).append({
            "run_id": run_id, "seq": seq, "ts": ts, "type": type_,
            "payload": json.loads(payload_json) if payload_json else {}, "id": ev_id,
        })
    return out
