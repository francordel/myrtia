"""`myrtia` command — start the console (API + web UI) with one command.

    uv run myrtia                 # http://127.0.0.1:8000/
    uv run myrtia --port 8010 --no-browser

A thin wrapper over uvicorn: it checks that a local Ollama is reachable (the
default council, chairman and judge run there) and opens the browser once the
server answers. Nothing here is required — `uvicorn myrtia.api.app:app` still
works the same.
"""

from __future__ import annotations

import argparse
import threading
import time
import urllib.request
import webbrowser

from myrtia.endpoints import OLLAMA_URL


def _ollama_running() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/", timeout=1.5) as resp:
            return resp.status == 200
    except OSError:
        return False


def _total_ram_gb() -> float | None:
    """Total RAM visible to this process (the Docker VM's, inside a container)."""
    try:
        import os
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1e9, 1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _open_when_ready(url: str, timeout: float = 300) -> None:
    """Open the browser once the server answers — startup (ARES, PyTorch) can take a while."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "health", timeout=2):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser(prog="myrtia", description="Start the Myrtia console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    if not _ollama_running():
        print(
            f"\n  ! Ollama isn't reachable at {OLLAMA_URL}/ — the default local\n"
            "    models won't answer. Start it (macOS: `brew services start ollama`) and\n"
            "    pull the demo models: `ollama pull qwen2.5:7b && ollama pull gemma3:1b`.\n"
            "    Remote endpoints still work.\n"
        )

    ram = _total_ram_gb()
    if ram is not None and ram < 6:
        print(
            f"\n  ! Only {ram:g} GB of RAM is available. The demo council loads three models\n"
            "    at once, and with this little memory a model may be killed mid-run\n"
            "    (\"llama-server ... signal: killed\"). In Docker, give the VM >=8 GB\n"
            "    (Docker Desktop: Settings -> Resources; Colima: `colima start --memory 8`).\n"
        )

    url = f"http://{args.host}:{args.port}/"
    print(f"\n  Myrtia console -> {url}\n")
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    uvicorn.run("myrtia.api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
