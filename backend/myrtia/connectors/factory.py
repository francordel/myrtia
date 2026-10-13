"""Target-connector factory.

Builds Myrtia's own OpenAI-compatible chat connector (see connectors/base.py) from a
small target spec. No ARES required — the core runs standalone; ARES / ares-council
are an optional plugin pack.

Myrtia target spec:
    {
        "kind": "openai_chat",
        "base_url": "http://127.0.0.1:11434/v1",   # Ollama / vLLM / hosted
        "model": "gpt-oss:120b",
        "api_key": null                             # optional
    }
"""

from __future__ import annotations

from typing import Any

from myrtia.connectors.base import (
    AnthropicMessagesConnector,
    Connector,
    HTTPAgentConnector,
    OpenAIChatConnector,
)

# Supported target kinds. "openai_chat" (default) covers Ollama / vLLM / OpenAI and any
# OpenAI-compatible proxy; "anthropic" speaks the native Messages API; "http_agent" is a
# guarded, configurable connector for arbitrary agent endpoints (issue #31).
_KINDS = {"openai_chat", "openai", "anthropic", "http_agent"}


def build_target_connector(spec: dict[str, Any]) -> Connector:
    """Return a Myrtia connector for the given target spec."""
    kind = spec.get("kind", "openai_chat")
    if kind not in _KINDS:
        raise ValueError(f"Unsupported target kind: {kind!r} (supported: {sorted(_KINDS)})")

    base_url = str(spec.get("base_url", "")).rstrip("/")
    from myrtia.security import url_block_reason
    reason = url_block_reason(base_url) if base_url else "missing base_url"
    if reason:
        raise ValueError(f"blocked target base_url: {reason}")

    model = spec.get("model", "")
    api_key = spec.get("api_key")
    if kind == "anthropic":
        return AnthropicMessagesConnector(
            base_url=base_url or "https://api.anthropic.com", model=model, api_key=api_key,
            max_tokens=int(spec.get("max_tokens", 1024) or 1024),
            name=f"myrtia-target-{model}")
    if kind == "http_agent":
        return HTTPAgentConnector(
            base_url=base_url, model=model, api_key=api_key,
            prompt_field=spec.get("prompt_field", "input"),
            response_path=spec.get("response_path", "output"),
            extra_body=spec.get("extra_body") or {},
            headers=spec.get("headers") or {},
            name=f"myrtia-agent-{model or 'target'}")
    return OpenAIChatConnector(
        base_url=base_url, model=model, api_key=api_key,
        name=f"myrtia-target-{model}")
