"""
Standalone smoke test: confirms GEMINI_API_KEY and TAVILY_API_KEY are
present and actually work, before running the full agent.

Run:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running as `python scripts/smoke_test.py` puts scripts/ on sys.path, not
# the project root, so `agent` wouldn't otherwise be importable — there's
# no installed package here (no setup.py/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from agent import config

    config.validate()
except RuntimeError as e:
    print(f"FAIL: {e}")
    sys.exit(1)

import google.generativeai as genai
from tavily import TavilyClient


def check_gemini() -> bool:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = model.generate_content(
            "Reply with exactly one word: ok",
            request_options={"timeout": 15},
        )
        text = response.text.strip()
    except Exception as e:
        print(f"FAIL: Gemini ({config.GEMINI_MODEL}) — {e}")
        return False
    print(f"PASS: Gemini ({config.GEMINI_MODEL}) — response: {text!r}")
    return True


def check_tavily() -> bool:
    # tavily-python hardcodes a 100s timeout internally (tavily/tavily.py);
    # TavilyClient.search() exposes no timeout override.
    try:
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        response = client.search(query="Shodh smoke test", max_results=1)
        n_results = len(response.get("results", []))
    except Exception as e:
        print(f"FAIL: Tavily — {e}")
        return False
    print(f"PASS: Tavily — {n_results} result(s) returned")
    return True


def main() -> None:
    gemini_ok = check_gemini()
    tavily_ok = check_tavily()

    if not (gemini_ok and tavily_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
