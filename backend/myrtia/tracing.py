"""Traces: each run as an OpenTelemetry trace (spec 009).

A run becomes a tree of spans — run, goal, turn, model call — with the run's other
events attached to the step they happened in. It is fed by the same two taps as the
metrics (spec 008): the event bus gives the structure (`observe_event`) and the
connector wrapper gives the model calls (`start_model_call`). Plugins need no tracing
code.

Rules kept here on purpose:
  * Off unless MYRTIA_TRACES=on, and the OpenTelemetry SDK is an optional extra
    (`uv run --extra otel myrtia`). Without it Myrtia runs as before and says why
    tracing is off.
  * Parents are explicit: each run keeps a stack of its open spans, found through the
    run bound to the worker's context (`telemetry.current_run`). No OpenTelemetry
    context is attached or detached, so events may arrive from any thread.
  * Content (prompts, replies, event text) is included by default, so a run can be
    audited; MYRTIA_TRACE_CONTENT=off keeps structure, timings, tokens and scores only.
    Keys and auth headers are never included and key-shaped strings are scrubbed.
  * Recording never raises: a tracing problem must not break a model call or a run.
  * A private tracer provider: Myrtia does not touch the process-wide one.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from types import SimpleNamespace
from typing import Any, Mapping

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://localhost:4318"
DEFAULT_MAX_CHARS = 20000
_INSTALL_HINT = ("the OpenTelemetry packages are not installed "
                 "(start Myrtia with `uv run --extra otel myrtia`)")
_ON = ("on", "1", "true", "yes", "otlp")
_OFF = ("off", "0", "false", "no")
# Event fields that stay when content is switched off: short identifiers, not text.
_SHORT_FIELDS = {"model", "id", "name", "stage", "status", "action", "decision", "sender",
                 "critic", "mutator", "winner", "approval_id", "event_type", "level"}
# Events that open or close spans instead of being attached to one.
_STRUCTURAL = {"run.started", "run.finished", "goal.started", "goal.finished", "turn.started"}

_lock = threading.RLock()
_state = SimpleNamespace(configured=False, enabled=False, reason="tracing is switched off",
                         endpoint=None, content=True, max_chars=DEFAULT_MAX_CHARS,
                         sdk=None, provider=None, tracer=None)
# run id -> stack of open spans, root first. Each entry: {"kind", "span", "score"}.
_runs: dict[str, list[dict[str, Any]]] = {}
_goal_counter: dict[str, int] = {}


# --- configuration -----------------------------------------------------------------
def _import_sdk() -> SimpleNamespace:
    """Import the optional SDK. Raises ImportError when the `otel` extra is missing."""
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    return SimpleNamespace(trace=trace, Resource=Resource, TracerProvider=TracerProvider,
                           BatchSpanProcessor=BatchSpanProcessor,
                           SimpleSpanProcessor=SimpleSpanProcessor)


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("myrtia")
    except Exception:  # noqa: BLE001
        return "unknown"


def _install(sdk: SimpleNamespace, processor: Any) -> None:
    provider = sdk.TracerProvider(resource=sdk.Resource.create(
        {"service.name": "myrtia", "service.version": _version()}))
    provider.add_span_processor(processor)
    _state.sdk, _state.provider = sdk, provider
    _state.tracer = provider.get_tracer("myrtia")
    _state.enabled = True


def _stop() -> None:
    provider = _state.provider
    _state.enabled, _state.provider, _state.tracer, _state.sdk = False, None, None, None
    _state.endpoint = None
    _runs.clear()
    _goal_counter.clear()
    if provider is not None:
        try:
            provider.shutdown()  # flushes what is still queued
        except Exception:  # noqa: BLE001
            logger.debug("could not shut the tracer down", exc_info=True)


def _flag(value: Any, default: bool) -> bool:
    v = str(value or "").strip().lower()
    return True if v in _ON else False if v in _OFF else default


def configure(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Switch tracing on or off from the environment. Never raises; `status()` says
    what happened."""
    env = os.environ if env is None else env
    with _lock:
        _stop()
        _state.configured = True
        _state.content = _flag(env.get("MYRTIA_TRACE_CONTENT"), True)
        try:
            _state.max_chars = max(1, int(env.get("MYRTIA_TRACE_MAX_CHARS") or DEFAULT_MAX_CHARS))
        except ValueError:
            _state.max_chars = DEFAULT_MAX_CHARS
        if not _flag(env.get("MYRTIA_TRACES"), False):
            _state.reason = "tracing is switched off (set MYRTIA_TRACES=on)"
            return status()
        endpoint = (env.get("MYRTIA_OTEL_ENDPOINT") or DEFAULT_ENDPOINT).strip().rstrip("/")
        from myrtia.security import url_block_reason
        blocked = url_block_reason(endpoint)
        if blocked:
            _state.reason = f"the export address is not allowed: {blocked}"
            return status()
        try:
            sdk = _import_sdk()
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint + "/v1/traces", timeout=5)
        except ImportError:
            _state.reason = _INSTALL_HINT
            return status()
        except Exception as exc:  # noqa: BLE001
            _state.reason = f"could not start the exporter: {type(exc).__name__}"
            return status()
        _install(sdk, sdk.BatchSpanProcessor(exporter))
        _state.endpoint, _state.reason = endpoint, "on"
        return status()


def use_exporter(exporter: Any, content: bool = True, max_chars: int = DEFAULT_MAX_CHARS) -> None:
    """Switch tracing on with a given span exporter, exported synchronously (tests)."""
    with _lock:
        _stop()
        sdk = _import_sdk()
        _install(sdk, sdk.SimpleSpanProcessor(exporter))
        _state.configured, _state.content, _state.max_chars = True, content, max(1, max_chars)
        _state.reason = "on"


def reset() -> None:
    """Switch tracing off and forget every open run."""
    with _lock:
        _stop()
        _state.configured, _state.content = True, True
        _state.max_chars, _state.reason = DEFAULT_MAX_CHARS, "tracing is switched off"


def shutdown() -> None:
    """Flush queued spans (application shutdown)."""
    with _lock:
        _stop()
        _state.reason = "tracing is switched off"


def _ready() -> bool:
    if not _state.configured:
        configure()
    return _state.enabled


def status() -> dict[str, Any]:
    """Whether tracing is on, where it exports, and why not when it is off."""
    if not _state.configured:
        configure()
    return {"enabled": _state.enabled, "reason": _state.reason, "endpoint": _state.endpoint,
            "content": _state.content}


# --- content rules -----------------------------------------------------------------
def _text(value: Any) -> tuple[str, bool]:
    """Scrub key-shaped strings and cut at the limit. Returns (text, was cut)."""
    from myrtia.store.runs import _scrub_value
    s = _scrub_value(str(value))
    if len(s) > _state.max_chars:
        return s[:_state.max_chars], True
    return s, False


def _attributes(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Event payload -> span or event attributes (`myrtia.<field>`)."""
    out: dict[str, Any] = {}
    cut = False
    for key, value in payload.items():
        if value is None:
            continue
        name = f"myrtia.{key}"
        if isinstance(value, (bool, int, float)):
            out[name] = value
        elif isinstance(value, str):
            if _state.content or key in _SHORT_FIELDS:
                out[name], was_cut = _text(value)
                cut = cut or was_cut
        elif _state.content:
            from myrtia.store.runs import _redact_secrets
            from copy import deepcopy
            try:
                dumped = json.dumps(_redact_secrets(deepcopy(value)), default=str)
            except Exception:  # noqa: BLE001
                dumped = str(value)
            out[name], was_cut = _text(dumped)
            cut = cut or was_cut
    if cut:
        out["myrtia.content.truncated"] = True
    return out


def _messages(prompt: Any) -> list[dict[str, str]]:
    if isinstance(prompt, list) and prompt and isinstance(prompt[0], dict):
        return [{"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
                for m in prompt]
    return [{"role": "user", "content": str(prompt)}]


def _messages_json(messages: list[dict[str, str]]) -> tuple[str, bool]:
    cut = False
    out = []
    for m in messages:
        content, was_cut = _text(m["content"])
        cut = cut or was_cut
        out.append({"role": m["role"], "content": content})
    return json.dumps(out), cut


# --- spans -------------------------------------------------------------------------
def _ns(ts: float) -> int:
    return int(float(ts) * 1e9)


def _start_span(name: str, parent: Any, attributes: dict[str, Any], start_ns: int,
                client: bool = False) -> Any:
    trace = _state.sdk.trace
    context = trace.set_span_in_context(parent) if parent is not None else None
    return _state.tracer.start_span(
        name, context=context, attributes=attributes, start_time=start_ns,
        kind=trace.SpanKind.CLIENT if client else trace.SpanKind.INTERNAL)


def _close_down_to(stack: list[dict[str, Any]], kinds: tuple[str, ...], end_ns: int) -> None:
    """End and pop the spans on top of the stack whose kind is in `kinds`."""
    while len(stack) > 1 and stack[-1]["kind"] in kinds:
        stack.pop()["span"].end(end_time=end_ns)


def _nearest(stack: list[dict[str, Any]], kinds: tuple[str, ...]) -> dict[str, Any]:
    return next((e for e in reversed(stack) if e["kind"] in kinds), stack[0])


def observe_event(event: Any) -> None:
    """Turn one published event into trace structure. Never raises."""
    try:
        if not _ready():
            return
        etype = getattr(event.type, "value", str(event.type))
        payload = event.payload if isinstance(event.payload, dict) else {}
        run_id, at = str(event.run_id), _ns(event.ts)
        with _lock:
            if etype == "run.started":
                spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
                target = spec.get("target") if isinstance(spec.get("target"), dict) else {}
                attack = str(spec.get("attack_id") or "unknown")
                attrs: dict[str, Any] = {
                    "myrtia.run.id": run_id, "myrtia.attack": attack,
                    "myrtia.target.model": str(target.get("model") or ""),
                    "myrtia.goals.count": len(spec.get("goals") or []),
                    "myrtia.purpose": str(spec.get("purpose") or ""),
                }
                if _state.content and spec.get("title"):
                    attrs["myrtia.run.title"] = _text(spec["title"])[0]
                span = _start_span(f"run {attack}", None, attrs, at)
                _runs[run_id] = [{"kind": "run", "span": span, "score": None}]
                _goal_counter[run_id] = 0
                return
            stack = _runs.get(run_id)
            if not stack:
                return
            if etype == "goal.started":
                _close_down_to(stack, ("turn", "goal"), at)
                index = payload.get("goal_index")
                if not isinstance(index, int) or isinstance(index, bool):
                    index = _goal_counter[run_id]
                _goal_counter[run_id] = index + 1
                attrs = {"myrtia.run.id": run_id, "myrtia.goal.index": index}
                attrs.update(_attributes({k: v for k, v in payload.items() if k != "goal_index"}))
                span = _start_span(f"goal {index}", stack[-1]["span"], attrs, at)
                stack.append({"kind": "goal", "span": span, "score": None})
            elif etype == "turn.started":
                _close_down_to(stack, ("turn",), at)
                turn = payload.get("turn")
                attrs = {"myrtia.run.id": run_id}
                attrs.update(_attributes(payload))
                span = _start_span(f"turn {turn if turn is not None else '?'}",
                                   stack[-1]["span"], attrs, at)
                stack.append({"kind": "turn", "span": span, "score": None})
            elif etype == "goal.finished":
                _close_down_to(stack, ("turn",), at)
                if stack[-1]["kind"] == "goal":
                    stack[-1]["span"].add_event(etype, _attributes(payload), timestamp=at)
                    _close_down_to(stack, ("goal",), at)
            elif etype == "run.finished":
                _close_down_to(stack, ("turn", "goal"), at)
                root = stack[0]["span"]
                status_ = str(payload.get("status") or "unknown")
                root.set_attribute("myrtia.run.status", status_)
                if status_ == "failed":
                    trace = _state.sdk.trace
                    root.set_status(trace.Status(trace.StatusCode.ERROR,
                                                 _text(payload.get("error") or "run failed")[0]))
                root.end(end_time=at)
                _runs.pop(run_id, None)
                _goal_counter.pop(run_id, None)
            else:
                stack[-1]["span"].add_event(etype, _attributes(payload), timestamp=at)
                score = payload.get("score")
                if (etype == "judge.scored" and isinstance(score, int)
                        and not isinstance(score, bool)):
                    owner = _nearest(stack, ("turn", "goal"))
                    if owner["score"] is None or score > owner["score"]:
                        owner["score"] = score
                        owner["span"].set_attribute("myrtia.judge.score", score)
    except Exception:  # noqa: BLE001 - tracing must never break a run
        logger.debug("could not trace an event", exc_info=True)


class _ModelCall:
    """An open model-call span; `end()` fills in the outcome and closes it."""

    def __init__(self, span: Any) -> None:
        self._span = span

    def end(self, ok: bool, error: str = "", response: str = "",
            prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        try:
            span = self._span
            if prompt_tokens > 0:
                span.set_attribute("gen_ai.usage.input_tokens", int(prompt_tokens))
            if completion_tokens > 0:
                span.set_attribute("gen_ai.usage.output_tokens", int(completion_tokens))
            if ok:
                if _state.content:
                    out, cut = _messages_json([{"role": "assistant", "content": str(response)}])
                    span.set_attribute("gen_ai.output.messages", out)
                    if cut:
                        span.set_attribute("myrtia.content.truncated", True)
            else:
                trace = _state.sdk.trace
                span.set_attribute("error.type", "model_call_failed")
                span.set_status(trace.Status(trace.StatusCode.ERROR, _text(error)[0][:300]))
            span.end()
        except Exception:  # noqa: BLE001
            logger.debug("could not close a model-call span", exc_info=True)


def start_model_call(role: str, model: str, prompt: Any) -> _ModelCall | None:
    """Open a span for one model call made inside a run. Returns None when tracing is
    off or the call belongs to no traced run. Never raises."""
    try:
        if not _ready():
            return None
        from myrtia import telemetry
        bound = telemetry.current_run()
        if bound is None:
            return None
        with _lock:
            stack = _runs.get(bound[0])
            if not stack:
                return None
            parent = stack[-1]["span"]
        model = str(model or "unknown")
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "chat", "gen_ai.request.model": model,
            "myrtia.role": str(role or "aux"), "myrtia.run.id": bound[0],
        }
        if _state.content:
            attrs["gen_ai.input.messages"], cut = _messages_json(_messages(prompt))
            if cut:
                attrs["myrtia.content.truncated"] = True
        return _ModelCall(_start_span(f"chat {model}", parent, attrs, time.time_ns(), client=True))
    except Exception:  # noqa: BLE001 - tracing must never break a model call
        logger.debug("could not open a model-call span", exc_info=True)
        return None
