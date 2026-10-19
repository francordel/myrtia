"""Chat-proxy router: forward chat completions to any OpenAI-compatible provider,
blocking (`/chat`) or streamed as SSE (`/chat/stream`). SSRF-guarded; the caller's
key is used only for the upstream call and never stored or logged."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from myrtia.api.deps import ChatRequest, require_token

router = APIRouter()


@router.post("/chat", dependencies=[Depends(require_token)])
def chat(body: ChatRequest) -> dict[str, Any]:
    """Proxy a chat completion to any OpenAI-compatible provider.

    Powers the in-app assistant. The key is used only to call the provider and is
    never stored or logged. Body: {base_url, model, messages, api_key?, max_tokens?}.
    """
    body = body.model_dump()
    import requests

    base = str(body.get("base_url", "")).rstrip("/")
    if not base or not body.get("model") or not body.get("messages"):
        return {"error": "base_url, model and messages are required"}
    from myrtia.security import url_block_reason
    blocked = url_block_reason(base)
    if blocked:
        return {"error": f"blocked base_url: {blocked}"}
    url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    headers = {"Content-Type": "application/json"}
    key = body.get("api_key")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": body["model"],
        "messages": body["messages"],
        "max_tokens": int(body.get("max_tokens", 1024)),
        "stream": False,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=120, allow_redirects=False)
        if r.status_code // 100 != 2:
            return {"error": f"provider {r.status_code}: {r.text[:300]}"}
        data = r.json()
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"reply": reply}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:300]}


@router.post("/chat/stream", dependencies=[Depends(require_token)])
def chat_stream(body: ChatRequest) -> StreamingResponse:
    """Streaming (token-by-token) chat completion, proxied as Server-Sent Events."""
    body = body.model_dump()
    import json as _json
    import requests

    base = str(body.get("base_url", "")).rstrip("/")
    url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    headers = {"Content-Type": "application/json"}
    key = body.get("api_key")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": body.get("model"), "messages": body.get("messages") or [],
        "max_tokens": int(body.get("max_tokens", 1024)), "stream": True,
    }

    from myrtia.security import url_block_reason
    _blocked = url_block_reason(base) if base else "missing base_url"

    def gen():
        if not base or not payload["model"] or not payload["messages"]:
            yield "data: " + _json.dumps({"error": "base_url, model and messages required"}) + "\n\n"
            return
        if _blocked:
            yield "data: " + _json.dumps({"error": f"blocked base_url: {_blocked}"}) + "\n\n"
            return
        try:
            with requests.post(url, json=payload, headers=headers, stream=True, timeout=120, allow_redirects=False) as r:
                if r.status_code // 100 != 2:
                    yield "data: " + _json.dumps({"error": f"provider {r.status_code}: {r.text[:200]}"}) + "\n\n"
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    s = line.decode("utf-8", "ignore")
                    if s.startswith("data: "):
                        s = s[6:]
                    if s.strip() == "[DONE]":
                        break
                    try:
                        d = _json.loads(s)
                        delta = (d.get("choices") or [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield "data: " + _json.dumps({"delta": delta}) + "\n\n"
                    except Exception:  # noqa: BLE001
                        continue
        except Exception as exc:  # noqa: BLE001
            yield "data: " + _json.dumps({"error": str(exc)[:200]}) + "\n\n"
        yield "data: " + _json.dumps({"done": True}) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
