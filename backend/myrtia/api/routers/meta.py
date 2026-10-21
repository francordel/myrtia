"""Meta / system router: the app shell, brand assets, health, machine capability,
plugin catalogue, hardware profiles, defenses and attack packs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from myrtia.api.deps import EstimateRequest, require_token
from myrtia.plugins.base import REGISTRY as PLUGINS

router = APIRouter()

# Serve the zero-build viewer at / so it shares the backend origin (no CORS/WS issues).
_STANDALONE = Path(__file__).resolve().parents[4] / "frontend" / "standalone.html"
_FRONTEND = Path(__file__).resolve().parents[4] / "frontend"
_ASSETS = {"icon.png", "icon-light.png", "icon-dark.png"}


@router.get("/")
async def index() -> FileResponse:
    # Never cache the app shell, so UI updates show up without a hard refresh.
    return FileResponse(_STANDALONE, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@router.get("/assets/{name}")
async def asset(name: str) -> FileResponse:
    # Serve a small whitelist of brand images (no path traversal, no route shadowing).
    if name not in _ASSETS:
        return JSONResponse({"error": "not found"}, status_code=404)  # type: ignore[return-value]
    return FileResponse(_FRONTEND / name)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _total_ram_gb() -> float | None:
    """Best-effort total physical RAM in GB, dependency-light and cross-platform."""
    try:
        import psutil  # optional; only in [dev]
        return round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        pass
    try:  # POSIX (macOS / Linux)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except (ValueError, AttributeError, OSError):
        pass
    try:  # Windows
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = _MS(); ms.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
        return round(ms.ullTotalPhys / 1e9, 1)
    except Exception:
        return None


def _nvidia_vram_gb() -> tuple[str | None, float | None]:
    """(name, VRAM GB) of the first NVIDIA GPU via nvidia-smi, or (None, None)."""
    import shutil
    import subprocess
    if not shutil.which("nvidia-smi"):
        return None, None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        line = (out.stdout or "").strip().splitlines()[0]
        name, mib = [x.strip() for x in line.split(",")]
        return name, round(float(mib) / 1024, 1)
    except Exception:
        return None, None


# Largest-first ladder of good local open-weight chat models with their approx Q4 memory (GB).
_MODEL_LADDER = [
    ("llama3.1:70b", 42.0), ("qwen2.5:32b", 21.0), ("gpt-oss:20b", 13.0),
    ("qwen2.5:14b", 10.0), ("qwen2.5:7b", 5.5), ("qwen2.5:3b", 2.5),
]


def _ollama_models() -> list[str] | None:
    """Models pulled into the local Ollama, or None when it isn't reachable."""
    import requests
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2, allow_redirects=False)
        r.raise_for_status()
        return sorted(m["name"] for m in (r.json().get("models") or []) if m.get("name"))
    except Exception:  # noqa: BLE001
        return None


@router.get("/system")
async def system_info() -> dict[str, Any]:
    """Local machine capability + a sensible default model, so the UI doesn't suggest a
    model too small (or too big) for the box running Myrtia."""
    import platform
    ram = _total_ram_gb()
    arch = platform.machine()
    osname = platform.system()
    apple_silicon = osname == "Darwin" and arch in ("arm64", "aarch64")
    gpu_name, vram = _nvidia_vram_gb()
    # Memory a local model can realistically use (headroom for the OS and app).
    if vram:
        budget = vram                       # NVIDIA: model lives in VRAM
    elif apple_silicon and ram:
        budget = ram * 0.7                  # unified memory, keep headroom
    elif ram:
        budget = ram * 0.6                  # CPU-only: works but slower
    else:
        budget = 0.0
    recommended = next((m for m, need in _MODEL_LADDER if budget >= need), "qwen2.5:3b")
    # The UI only switches roles to the recommendation once it's pulled — otherwise a
    # first run would fail with "model not found" (the quick start pulls qwen2.5:3b).
    installed = _ollama_models()
    return {
        "os": osname, "arch": arch, "apple_silicon": apple_silicon,
        "cpu_count": os.cpu_count(), "ram_gb": ram,
        "gpu": ({"name": gpu_name, "vram_gb": vram} if vram else None),
        "model_budget_gb": round(budget, 1) if budget else None,
        "recommended_model": recommended,
        "ollama_models": installed,
        "recommended_installed": bool(installed) and recommended in installed,
        "note": (None if ram else "Could not read system memory; defaulting conservatively."),
    }


@router.get("/profiles")
async def profiles() -> dict[str, Any]:
    """Hardware profiles used to estimate run time (issue #38)."""
    from myrtia.estimate import HARDWARE_PROFILES, DEFAULT_PROFILE
    return {"default": DEFAULT_PROFILE,
            "profiles": [{"id": k, "label": v["label"], "per_call": v["per_call"],
                          "parallel": v.get("parallel", 1)} for k, v in HARDWARE_PROFILES.items()]}


@router.post("/estimate")
async def estimate(body: EstimateRequest) -> dict[str, Any]:
    """Rough wall-clock estimate for a run given its config and a hardware profile."""
    body = body.model_dump()
    from myrtia.estimate import estimate_run, DEFAULT_PROFILE
    return estimate_run(body.get("attack_id", ""), body.get("attack_config") or {},
                        int(body.get("n_goals") or 0), body.get("profile") or DEFAULT_PROFILE)


@router.get("/defenses")
async def defenses() -> dict[str, Any]:
    """List the literature defenses (shields) that can be chained in front of the target."""
    from myrtia.defenses import list_defenses
    return {"defenses": list_defenses()}


@router.get("/packs")
async def packs() -> dict[str, Any]:
    """List optional attack-toolkit packs (ARES/ares-council, garak, PyRIT) + installed state."""
    from myrtia import packs as _packs
    return {"packs": _packs.list_packs()}


@router.post("/packs/{pack_id}/install", dependencies=[Depends(require_token)])
async def install_pack(pack_id: str) -> dict[str, Any]:
    """Install one allowlisted pack (pip + register). Only ids in the curated registry."""
    import asyncio as _asyncio
    from myrtia import packs as _packs
    # pip install can take a while — run it off the event loop.
    result = await _asyncio.get_running_loop().run_in_executor(None, _packs.install_pack, pack_id)
    return result


@router.get("/plugins")
async def plugins() -> dict[str, Any]:
    return {
        "plugins": [
            {"id": s.id, "description": s.description, "config_schema": s.config_schema,
             "paper": getattr(s, "paper", ""), "how": getattr(s, "how", []),
             "templates": getattr(s, "templates", {})}
            for s in PLUGINS.values()
        ]
    }
