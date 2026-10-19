"""Shared live-streaming + cancellation seam for attack strategies.

Every Myrtia attack plugin needs the same two orchestrator hooks: an event emitter
(so the run streams proposals/responses/judgements to the live UI) and an optional
cancel check (so a stop request ends the run). They were copy-pasted verbatim into
each plugin's strategy class; `LiveAttack` holds the single implementation so a plugin
just inherits it.

Usage: `class MyAttackLive(LiveAttack): ...`. The defaults are class attributes, so an
instance that never gets an emitter or cancel check simply reads `None` — no `__init__`
boilerplate required.
"""

from __future__ import annotations

from typing import Any


class LiveAttack:
    """Mixin providing the `set_event_emitter`/`_emit` and `set_cancel_check`/`_is_cancelled` seam."""

    _on_event: Any = None
    _cancelled: Any = None

    # --- live event streaming (orchestrator wires set_event_emitter) ---
    def set_event_emitter(self, emit: Any) -> None:
        self._on_event = emit

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event_type, payload)
        except Exception:  # noqa: BLE001 — streaming must never break the attack
            pass

    # --- cooperative cancellation (orchestrator wires set_cancel_check) ---
    def set_cancel_check(self, fn: Any) -> None:
        self._cancelled = fn

    def _is_cancelled(self) -> bool:
        try:
            return bool(self._cancelled and self._cancelled())
        except Exception:  # noqa: BLE001
            return False
