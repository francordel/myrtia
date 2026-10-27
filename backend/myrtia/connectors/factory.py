"""Target-connector factory.

Builds Myrtia's own OpenAI-compatible chat connector (see connectors/base.py) from a
small target spec. No ARES required — the core runs standalone; ARES / ares-council
are an optional plugin pack.

Myrtia target spec:
    {
        "kind": "openai_chat",
        "base_url": "http://127.0.0.1:11434/v1",   # Ollama / vLLM / hosted
        "model": "gpt-oss:120b",
        "api_key": null,                            # optional
        "auth_header": null,                        # optional: send the key in this header
                                                    # (e.g. "RITS_API_KEY") instead of Bearer
        "headers": {}                               # optional extra request headers
    }
"""

from __future__ import annotations

import re
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


_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9-_]{1,64}$")


def role_auth(config: dict[str, Any], role: str, endpoint: str | None) -> tuple[str | None, str | None]:
    """Resolve (api_key, auth_header) for an auxiliary role ("aux" = attacker/helper,
    "judge" = evaluator) from an attack_config.

    A role's own `<role>_api_key` / `<role>_auth_header` win. Otherwise the target's
    credentials are inherited, but only when the role talks to the target's own
    endpoint — so a cloud key is never sent to a different host. Configs without
    `target_base_url` (direct API callers) keep the old always-inherit behaviour."""
    own = config.get(f"{role}_api_key")
    if own:
        return own, config.get(f"{role}_auth_header") or None
    target_url = config.get("target_base_url")
    if target_url and str(endpoint or "").rstrip("/") != str(target_url).rstrip("/"):
        return None, None
    return config.get("api_key"), config.get("auth_header") or None


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
    auth_header = spec.get("auth_header") or None
    if auth_header is not None and not _HEADER_NAME_RE.match(str(auth_header)):
        raise ValueError(f"invalid auth_header name: {auth_header!r}")
    return OpenAIChatConnector(
        base_url=base_url, model=model, api_key=api_key,
        headers=spec.get("headers") or {}, auth_header=auth_header,
        name=f"myrtia-target-{model}")
