"""Where the default local models live — one setting for the whole app.

Every role (attacker, chairman, judge, defence model, target) that doesn't name its
own endpoint uses this Ollama. Set MYRTIA_OLLAMA_URL to point Myrtia elsewhere: an
Ollama on the Docker host (`http://host.docker.internal:11434`) or on a GPU server.
Either the server root or its `/v1` URL is accepted.
"""

from __future__ import annotations

import os

_DEFAULT = "http://127.0.0.1:11434"

_url = (os.getenv("MYRTIA_OLLAMA_URL") or _DEFAULT).strip().rstrip("/")
if _url.endswith("/v1"):
    _url = _url[:-3]

OLLAMA_URL = _url                 # native Ollama API root (/api/tags, /api/pull)
OLLAMA_V1 = _url + "/v1"          # OpenAI-compatible endpoint used by every role

# Default local model for every role (attacker, chairman, judge) when the user
# doesn't choose one. Native installs pull qwen2.5:7b (a capable attacker most
# machines can run); the Docker compose sets this to qwen2.5:3b, since models run
# on CPU in the VM there. Targets default to gemma3:1b separately.
DEFAULT_MODEL = (os.getenv("MYRTIA_DEFAULT_MODEL") or "qwen2.5:7b").strip()
