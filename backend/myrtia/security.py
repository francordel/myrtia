"""Small security helpers shared across the backend.

SSRF note: Myrtia's legitimate targets include local (127.0.0.1) and self-hosted
LAN/private endpoints (Ollama, vLLM), so we deliberately do NOT block loopback or
RFC1918 ranges. We only block cloud link-local metadata (169.254.0.0/16 and the
common metadata hostnames), which is never a legitimate model endpoint and is the
highest-value SSRF target (instance credentials).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_METADATA_HOSTS = {
    "metadata.google.internal", "metadata", "metadata.goog",
}


def url_block_reason(url: str) -> str | None:
    """Return a reason string if the URL must be blocked, else None."""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return "invalid url"
    scheme = (p.scheme or "").lower()
    if scheme not in ("http", "https"):
        return f"scheme {scheme or '(none)'} not allowed (use http/https)"
    host = (p.hostname or "").lower()
    if not host:
        return "missing host"
    if host in _METADATA_HOSTS:
        return "cloud metadata host blocked"
    # Resolve and reject any address in the link-local range (metadata services).
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:  # noqa: BLE001 - let the request itself fail later
        return None
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            continue
        if ip.is_link_local:  # 169.254.0.0/16 / fe80::/10 — cloud metadata
            return "link-local / metadata address blocked"
    return None
