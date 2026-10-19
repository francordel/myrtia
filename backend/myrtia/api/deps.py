"""Shared API dependencies and configuration.

Kept free of any `app`/router import so every router can depend on it without a
cycle. Holds the app version, the optional access-token gate and the request
models — the pieces more than one router needs.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict

APP_VERSION = "0.0.1"

# Optional access gate (issue #13). Off by default for local single-operator use;
# set MYRTIA_TOKEN in the environment to require it on mutating endpoints. CORS is
# already restricted to local origins (see the middleware in app.py).
_ACCESS_TOKEN = os.getenv("MYRTIA_TOKEN") or ""


def require_token(x_myrtia_token: str | None = Header(default=None),
                  token: str | None = None) -> None:
    if _ACCESS_TOKEN and x_myrtia_token != _ACCESS_TOKEN and token != _ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid access token")


class _Body(BaseModel):
    """Base request model — tolerant (extra fields allowed) so the API stays
    forgiving while every endpoint still gets a typed, documented schema (issue #26)."""
    model_config = ConfigDict(extra="allow")


class ChatRequest(_Body):
    base_url: str = ""
    model: str = ""
    messages: list = []
    api_key: str | None = None
    max_tokens: int = 1024


class ModelPullRequest(_Body):
    base_url: str = ""
    name: str = ""


class BehaviorParseRequest(_Body):
    content: str = ""
    filename: str = ""
    theme: str = ""


class RunRequest(_Body):
    attack_id: str = ""
    title: str = ""
    goals: list = []
    target: dict = {}
    attack_config: dict = {}
    defenses: list = []
    judge_id: str | None = None
    theme: str = ""
    purpose: str = "unreviewed"
    goal_datasets: list[str] = []


class PurposeRequest(_Body):
    purpose: str = ""


class PreflightRequest(_Body):
    target: dict = {}


class ApprovalDecision(_Body):
    decision: bool = False


class EstimateRequest(_Body):
    attack_id: str = ""
    attack_config: dict = {}
    n_goals: int = 1
    profile: str = ""
