"""
Lists Gemini models the API reports supporting generateContent. Free-tier
model availability changes over time — run this whenever Gemini calls
start failing with quota/model errors, and update GEMINI_MODEL in .env
accordingly.

Caveat: this list is NOT a guarantee of callability. A model can appear
here while still 404ing on generate_content with "no longer available to
new users" — the API distinguishes "exists and supports the method" from
"this key/project may call it," and only the latter matters. Prefer a
"-latest" alias (e.g. gemini-flash-latest) over a pinned version below;
if picking a pinned version, confirm it actually works with a real
generate_content call (see scripts/smoke_test.py) before committing to it.
Or pass --probe (below) to check callability directly instead of guessing.

Run:
    python scripts/list_models.py
    python scripts/list_models.py --probe   # makes one real call per model
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Running as `python scripts/list_models.py` puts scripts/ on sys.path, not
# the project root, so `agent` wouldn't otherwise be importable — there's
# no installed package here (no setup.py/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.generativeai as genai
from google.api_core.exceptions import NotFound, ResourceExhausted

from agent import config

config.validate()
genai.configure(api_key=config.GEMINI_API_KEY)

# --probe only tests text-generation models — skip TTS/image/robotics/music/
# computer-use variants, which use generateContent but aren't what
# GEMINI_MODEL is for here.
_PROBE_SKIP_KEYWORDS = ("image", "tts", "robotics", "lyria", "computer-use", "nano-banana")

# Between live probe calls, so we don't trip a rate limit ourselves on top
# of whatever quota problem we're diagnosing.
_PROBE_DELAY_SECONDS = 2.0
_PROBE_TIMEOUT_SECONDS = 15.0

_STATUS_ORDER = {"OK": 0, "404-unavailable": 1, "429-no-quota": 2, "other-error": 3}


def _generate_content_models() -> list[genai.types.Model]:
    return [m for m in genai.list_models() if "generateContent" in m.supported_generation_methods]


def _short_name(model: genai.types.Model) -> str:
    return model.name.removeprefix("models/")


def _is_probe_candidate(short_name: str) -> bool:
    if not short_name.startswith("gemini-"):
        return False
    lowered = short_name.lower()
    return not any(keyword in lowered for keyword in _PROBE_SKIP_KEYWORDS)


def probe_model(short_name: str) -> tuple[str, str]:
    """Makes one minimal generate_content call. Returns (status, detail),
    where status is OK / 404-unavailable / 429-no-quota / other-error and
    detail is the reply text (OK) or the exception class name (otherwise)."""
    try:
        model = genai.GenerativeModel(short_name)
        response = model.generate_content("ok", request_options={"timeout": _PROBE_TIMEOUT_SECONDS})
        return "OK", response.text.strip()
    except NotFound as e:
        return "404-unavailable", type(e).__name__
    except ResourceExhausted as e:
        return "429-no-quota", type(e).__name__
    except Exception as e:
        return "other-error", type(e).__name__


def list_models() -> None:
    print("Models supporting generateContent:")
    configured_model_found = False
    for model in _generate_content_models():
        short_name = _short_name(model)
        marker = " <- currently configured" if short_name == config.GEMINI_MODEL else ""
        if marker:
            configured_model_found = True
        print(f"  {short_name:<30} {model.display_name}{marker}")

    if not configured_model_found:
        print(f"\nWARNING: configured GEMINI_MODEL '{config.GEMINI_MODEL}' was not in the list above.")


def probe_models() -> None:
    candidates = [
        (_short_name(m), m.display_name) for m in _generate_content_models() if _is_probe_candidate(_short_name(m))
    ]
    print(f"Probing {len(candidates)} text-generation models (one real call each, {_PROBE_DELAY_SECONDS}s apart)...\n")

    results: list[tuple[str, str, str, str]] = []
    for i, (short_name, display_name) in enumerate(candidates):
        status, detail = probe_model(short_name)
        results.append((short_name, display_name, status, detail))
        if i < len(candidates) - 1:
            time.sleep(_PROBE_DELAY_SECONDS)

    results.sort(key=lambda r: (_STATUS_ORDER[r[2]], r[0]))

    for short_name, display_name, status, detail in results:
        marker = " <- currently configured" if short_name == config.GEMINI_MODEL else ""
        print(f"  {short_name:<30} {status:<16} {detail}{marker}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--probe",
        action="store_true",
        help="make one real generate_content call per text model instead of just listing metadata",
    )
    args = parser.parse_args()

    print(f"Configured GEMINI_MODEL: {config.GEMINI_MODEL}\n")
    if args.probe:
        probe_models()
    else:
        list_models()


if __name__ == "__main__":
    main()
