# Myrtia console (API + web UI) — the image `compose.yaml` runs next to Ollama.
#
#   docker compose up        # from a clone, or with just compose.yaml downloaded
#
# PyTorch (pulled in by ARES core) comes from the CPU wheel index: the models run in
# Ollama, so Myrtia never needs CUDA, and this keeps the image several GB smaller.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    MYRTIA_DB=/data/myrtia.db \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so code edits don't invalidate the (large) dependency layer.
COPY backend/pyproject.toml backend/README.md backend/
COPY backend/vendor backend/vendor
RUN mkdir -p backend/myrtia && touch backend/myrtia/__init__.py \
 && uv venv /app/.venv \
 && uv pip install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --index-strategy unsafe-best-match \
      -e backend -e backend/vendor/ares-council

# Editable installs: the backend finds frontend/ relative to its own source tree.
COPY backend/myrtia backend/myrtia
COPY frontend frontend

RUN useradd --create-home --uid 1000 myrtia \
 && mkdir -p /data && chown myrtia /data
USER myrtia
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["myrtia", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
