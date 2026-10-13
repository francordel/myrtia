"""Myrtia's own target connector — no ARES required.

Myrtia used to build its target connector from ARES's RESTfulConnector, which made
ARES a hard dependency for every run. This module provides a small, self-contained
OpenAI-compatible chat client with the same tiny surface the plugins rely on
(`generate()` returning an object with `.status`, `.response`, `.error_message`),
so the core (all built-in attacks + the graph engine) runs with zero ARES. ARES /
ares-council become an *optional* plugin pack (see myrtia/plugins/council.py).

`Status` is Myrtia's own two-value enum, a drop-in for `ares.utils.Status` — the
plugins only ever compare against SUCCESS.
"""

from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import requests


class Status(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class Response:
    """What a connector returns. Mirrors the shape the plugins read."""
    status: Status
    response: str = ""
    error_message: str = ""


class OpenAIChatConnector:
    """Minimal OpenAI-compatible chat connector (Ollama, vLLM, OpenAI, any /v1).

    `generate()` accepts either a single prompt string or a full conversation as a
    list of {role, content} message dicts (multi-turn / crescendo), and returns a
    `Response`. Never raises: transport/HTTP errors come back as `Status.ERROR`."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 timeout: int = 120, name: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        # ares-council reads target_connector.config["name"]; keep a compatible dict.
        self.config: dict[str, Any] = {"name": name or f"myrtia-target-{model}",
                                        "model": model, "base_url": self.base_url}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def _messages(self, prompt: Any) -> list[dict]:
        if isinstance(prompt, list) and prompt and isinstance(prompt[0], dict):
            return prompt  # a conversation passed straight through
        return [{"role": "user", "content": str(prompt)}]

    def generate(self, prompt: Any, **_kwargs: Any) -> Response:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": self._messages(prompt)}
        # Auxiliary council calls need explicit budgets; target calls remain
        # unchanged unless their caller requests these standard OpenAI fields.
        max_tokens = _kwargs.get("max_tokens")
        if isinstance(max_tokens, int) and not isinstance(max_tokens, bool) and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        temperature = _kwargs.get("temperature")
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
            payload["temperature"] = temperature
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                              headers=headers, timeout=self.timeout,
                              allow_redirects=False)
        except requests.RequestException as e:  # noqa: BLE001
            return Response(Status.ERROR, error_message=f"request failed: {e}")
        if r.status_code >= 400:
            return Response(Status.ERROR, error_message=f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            data = r.json()
        except ValueError:
            return Response(Status.ERROR, error_message="non-JSON response from endpoint")
        u = data.get("usage") or {}
        self.tokens["prompt"] += int(u.get("prompt_tokens", 0) or 0)
        self.tokens["completion"] += int(u.get("completion_tokens", 0) or 0)
        self.tokens["total"] += int(u.get("total_tokens", 0) or 0)
        self.tokens["calls"] += 1
        text = _extract_text(data)
        if text is None:
            return Response(Status.ERROR, error_message=f"no content in response: {str(data)[:200]}")
        return Response(Status.SUCCESS, response=text)


def _extract_text(data: dict) -> str | None:
    """Pull the assistant text out of an OpenAI-compatible chat completion."""
    try:
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # some servers return content as a list of parts
        if isinstance(content, list):
            return "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if isinstance(choice.get("text"), str):  # legacy completion shape
            return choice["text"]
    except Exception:  # noqa: BLE001
        return None
    return None


class AnthropicMessagesConnector:
    """Native Anthropic Messages API connector (issue #31).

    Some targets are only reachable through Anthropic's own /v1/messages shape
    (x-api-key + anthropic-version headers, a content-block response) rather than an
    OpenAI-compatible proxy. Same tiny surface as OpenAIChatConnector: generate()
    returns a Response and never raises.
    """

    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 timeout: int = 120, name: str | None = None, max_tokens: int = 1024,
                 version: str = "2023-06-01") -> None:
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = int(max_tokens or 1024)
        self.version = version
        self.config: dict[str, Any] = {"name": name or f"myrtia-target-{model}",
                                        "model": model, "base_url": self.base_url}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def _messages(self, prompt: Any) -> list[dict]:
        if isinstance(prompt, list) and prompt and isinstance(prompt[0], dict):
            # keep only user/assistant turns; Anthropic takes the system prompt separately
            return [{"role": m.get("role", "user"), "content": str(m.get("content", ""))}
                    for m in prompt if m.get("role") in ("user", "assistant")] or [{"role": "user", "content": ""}]
        return [{"role": "user", "content": str(prompt)}]

    def generate(self, prompt: Any, **_kwargs: Any) -> Response:
        headers = {"Content-Type": "application/json", "anthropic-version": self.version}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        payload = {"model": self.model, "max_tokens": self.max_tokens, "messages": self._messages(prompt)}
        try:
            r = requests.post(f"{self.base_url}/v1/messages", json=payload, headers=headers, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as e:  # noqa: BLE001
            return Response(Status.ERROR, error_message=f"request failed: {e}")
        if r.status_code >= 400:
            return Response(Status.ERROR, error_message=f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            data = r.json()
        except ValueError:
            return Response(Status.ERROR, error_message="non-JSON response from endpoint")
        u = data.get("usage") or {}
        self.tokens["prompt"] += int(u.get("input_tokens", 0) or 0)
        self.tokens["completion"] += int(u.get("output_tokens", 0) or 0)
        self.tokens["total"] += int(u.get("input_tokens", 0) or 0) + int(u.get("output_tokens", 0) or 0)
        self.tokens["calls"] += 1
        parts = data.get("content") or []
        text = "".join(b.get("text", "") for b in parts if isinstance(b, dict) and b.get("type") == "text")
        if not text and isinstance(parts, list) and parts and isinstance(parts[0], dict):
            text = str(parts[0].get("text", ""))
        if not text:
            return Response(Status.ERROR, error_message=f"no content in response: {str(data)[:200]}")
        return Response(Status.SUCCESS, response=text)


def _dig(obj: Any, path: str) -> Any:
    """Walk a dot-path (with optional [i] indices) into a nested dict/list."""
    cur = obj
    for part in path.split("."):
        if not part:
            continue
        m = re.match(r"([^\[]*)((?:\[\d+\])*)$", part)
        key = m.group(1) if m else part
        if key:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        for idx in re.findall(r"\[(\d+)\]", (m.group(2) if m else "")):
            if isinstance(cur, list) and int(idx) < len(cur):
                cur = cur[int(idx)]
            else:
                return None
    return cur


class HTTPAgentConnector:
    """Generic, guarded HTTP connector for arbitrary agent endpoints (issue #31).

    For targets that are not OpenAI- or Anthropic-shaped: POST a JSON body built from
    a configurable prompt field and read the reply from a configurable dot-path. The
    URL is SSRF-checked by the factory before this is built. Spec fields:
      prompt_field   (default "input")  — where the prompt goes in the request body
      response_path  (default "output") — dot-path to the reply text in the response
      extra_body     (dict)             — merged into the request body
      headers        (dict)             — extra request headers
    """

    def __init__(self, base_url: str, model: str = "", api_key: str | None = None,
                 timeout: int = 120, name: str | None = None, prompt_field: str = "input",
                 response_path: str = "output", extra_body: dict | None = None,
                 headers: dict | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.prompt_field = prompt_field or "input"
        self.response_path = response_path or "output"
        self.extra_body = dict(extra_body or {})
        self.extra_headers = dict(headers or {})
        self.config: dict[str, Any] = {"name": name or f"myrtia-agent-{model or 'target'}",
                                       "model": model, "base_url": self.base_url}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def _prompt_text(self, prompt: Any) -> str:
        if isinstance(prompt, list) and prompt and isinstance(prompt[0], dict):
            for m in reversed(prompt):
                if m.get("role") == "user":
                    return str(m.get("content", ""))
            return str(prompt[-1].get("content", ""))
        return str(prompt)

    def generate(self, prompt: Any, **_kwargs: Any) -> Response:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers.setdefault("Authorization", f"Bearer {self.api_key}")
        body = {**self.extra_body, self.prompt_field: self._prompt_text(prompt)}
        if self.model:
            body.setdefault("model", self.model)
        try:
            r = requests.post(self.base_url, json=body, headers=headers, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as e:  # noqa: BLE001
            return Response(Status.ERROR, error_message=f"request failed: {e}")
        if r.status_code >= 400:
            return Response(Status.ERROR, error_message=f"HTTP {r.status_code}: {r.text[:300]}")
        self.tokens["calls"] += 1
        try:
            data = r.json()
        except ValueError:
            return Response(Status.SUCCESS, response=r.text)  # plain-text agent reply
        text = _dig(data, self.response_path)
        if isinstance(text, (dict, list)):
            text = _json.dumps(text)
        if text is None or text == "":
            return Response(Status.ERROR, error_message=f"no value at response_path '{self.response_path}': {str(data)[:200]}")
        return Response(Status.SUCCESS, response=str(text))
