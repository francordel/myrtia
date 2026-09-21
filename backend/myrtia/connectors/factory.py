"""Target-connector factory.

Myrtia does not reimplement connectors: it builds **ARES** connectors from a small
Myrtia target spec. ARES already ships `RESTfulConnector` (OpenAI-compatible chat via
`api_endpoint` + `request_template`), which is exactly what CouncilAttack's target is
in the experiments (vLLM / Ollama `/v1` / hosted APIs).

ARES is imported lazily so the rest of the backend imports without ARES installed.

Myrtia target spec (MVP):
    {
        "kind": "openai_chat",
        "base_url": "http://127.0.0.1:11434/v1",   # Ollama / vLLM / hosted
        "model": "gpt-oss:120b",
        "api_key": null                             # optional
    }
"""

from __future__ import annotations

import json
from typing import Any


def build_target_connector(spec: dict[str, Any]) -> Any:
    """Return an ARES Connector for the given Myrtia target spec."""
    kind = spec.get("kind", "openai_chat")
    if kind != "openai_chat":
        raise ValueError(f"Unsupported target kind for MVP: {kind!r}")

    base_url = spec["base_url"].rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    model = spec["model"]
    api_key = spec.get("api_key")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    ares_config = {
        "type": "ares.connectors.restful_connector.RESTfulConnector",
        "name": f"myrtia-target-{model}",
        "api_config": {
            "api_endpoint": endpoint,
            "request_method": "post",
            # header / request_template must be dicts here: ARES's init_rest_params
            # stores them as-is (it does NOT json.loads), and _fill_template calls
            # dict(...) on them. The json.dumps in ARES's docstring is misleading.
            "header": headers,
            # $MESSAGES is replaced by ARES with the chat message list.
            "request_template": {"model": model, "messages": "$MESSAGES"},
            # Default extractor reads choices[0].message.content (OpenAI-compatible).
            "response_type": "json",
            "response_format": "json",
            "timeout": 120,
            "other": {},
        },
    }

    # Lazy import: keeps the backend importable without ARES present.
    from ares.connectors.restful_connector import RESTfulConnector

    class ChatRESTfulConnector(RESTfulConnector):
        """RESTfulConnector that also accepts a conversation (list of role/content
        dicts) in generate(). ARES's base rejects any list as a batch, which breaks
        multi-turn / crescendo attacks that send an accumulated conversation as one
        call. `_preprocess_for_chat_template` already handles a message list, so we
        just relax the guard: a list of message dicts is a single conversation, and
        a list of strings is still a batch (delegated to the base check)."""

        @staticmethod
        def _check_if_list(prompt):  # type: ignore[override]
            if isinstance(prompt, list) and prompt and isinstance(prompt[0], dict):
                return True  # single multi-turn conversation
            return RESTfulConnector._check_if_list(prompt)

    return ChatRESTfulConnector(ares_config)
