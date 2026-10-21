"""`myrtia` command — start the console (API + web UI) with one command.

    uv run myrtia                 # http://127.0.0.1:8000/
    uv run myrtia --port 8010 --no-browser

A thin wrapper over uvicorn: it checks that a local Ollama is reachable (the
default council, chairman and judge run there) and opens the browser once the
server is listening. Nothing here is required — `uvicorn myrtia.api.app:app` still
works the same.
"""

from __future__ import annotations

import argparse
import threading
import urllib.request
import webbrowser

OLLAMA_URL = "http://127.0.0.1:11434/"


def _ollama_running() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_URL, timeout=1.5) as resp:
            return resp.status == 200
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(prog="myrtia", description="Start the Myrtia console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    if not _ollama_running():
        print(
            "\n  ! Ollama isn't reachable at http://127.0.0.1:11434/ — the default local\n"
            "    models won't answer. Start it (macOS: `brew services start ollama`) and\n"
            "    pull the demo model: `ollama pull qwen2.5:3b`. Remote endpoints still work.\n"
        )

    url = f"http://{args.host}:{args.port}/"
    print(f"\n  Myrtia console -> {url}\n")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    import uvicorn

    uvicorn.run("myrtia.api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
