"""
Centralized runtime configuration: loads .env once from an explicit path,
exposes settings, and validates required API keys on demand.

Importing this module never crashes by itself — call validate() from any
module that actually talks to Gemini or Tavily, so modules that only need
the non-secret constants (e.g. agent/state.py) stay import-safe without a
.env present.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# agent/config.py -> project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# "-latest" alias, not a pinned version: pinned versions get retired
# (see .env.example) and, per scripts/list_models.py, being *listed* by
# the API doesn't mean this key can actually call it — several pinned
# models 404 with "no longer available to new users" while still
# appearing in the list. Aliases stay pointed at a live model.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# Agent state machine guards, relocated from agent/state.py.
MAX_ITERATIONS = 6
MAX_TOKENS = 40_000

_REQUIRED = {"GEMINI_API_KEY": GEMINI_API_KEY, "TAVILY_API_KEY": TAVILY_API_KEY}


def validate() -> None:
    """Raise if a required API key is missing. Call this at the top of any
    module that actually calls Gemini or Tavily."""
    missing = [name for name, value in _REQUIRED.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )
