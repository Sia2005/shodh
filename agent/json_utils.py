"""
Shared JSON-mode plumbing for the Gemini calls in planner.py and
synthesizer.py.

Motivation: a 30-question eval run (evals/results.md) hit malformed JSON
on 6 of 30 planner calls -- unquoted array elements, a stray "=" after the
opening bracket, a nested [[...]] wrapper, and once the entire response in
Hindi. Prompt wording alone doesn't make that go away, so the fix is
mechanical: strip the junk we can strip deterministically, and re-prompt
once for the junk we can't.

Deliberately not a framework abstraction -- one function, no registry, no
retry policy objects. Bounded at exactly one retry, per the project's
"every tool call must be bounded" rule.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import google.generativeai as genai

_RETRY_INSTRUCTION = (
    "Your previous response was not valid JSON. Return ONLY the JSON, "
    "no other text, in English."
)


def strip_to_json(raw: str) -> str:
    """Best-effort removal of the wrappers Gemini adds around JSON despite
    being told not to. Only handles junk that can be stripped without
    guessing at intent -- anything ambiguous (e.g. unquoted array elements)
    is left alone for the retry to handle."""
    text = raw.strip()

    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    text = text.strip()

    # Observed in the wild: '[="What are the results...", "..."]' -- a stray
    # '=' immediately after the opening bracket.
    if text.startswith("[=") or text.startswith("{="):
        text = text[0] + text[2:]

    # Trim prose before/after the payload ("Here's the JSON:" and friends).
    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    if starts:
        start = min(starts)
        end = text.rfind("]" if text[start] == "[" else "}")
        text = text[start : end + 1] if end > start else text[start:]

    return text.strip()


def generate_json(
    model: genai.GenerativeModel,
    prompt: str,
    *,
    what: str,
    validate: Callable[[Any], Any] | None = None,
    timeout: float = 60.0,
) -> Any:
    """Calls generate_content and parses the response as JSON, re-prompting
    exactly once if the first attempt doesn't parse (or fails `validate`).

    `what` names the caller for error messages ("Planner", "Synthesizer").
    `validate` gets the parsed value and returns the value to use — so it
    can repair shapes that are fixable without another API call (observed:
    sub-questions nested in an extra list, flattened by the planner's
    callback). It should raise ValueError for anything unrepairable; that
    triggers the same single retry a parse failure does.

    Raises ValueError if the second attempt fails too."""

    def attempt(text: str) -> Any:
        parsed = json.loads(strip_to_json(text))
        if validate is not None:
            parsed = validate(parsed)
        return parsed

    response = model.generate_content(prompt, request_options={"timeout": timeout})
    raw = response.text.strip()
    try:
        return attempt(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    retry_response = model.generate_content(
        f"{prompt}\n\n{_RETRY_INSTRUCTION}\n\nYour last output was:\n{raw}",
        request_options={"timeout": timeout},
    )
    retry_raw = retry_response.text.strip()
    try:
        return attempt(retry_raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{what} did not return valid JSON after one retry: {retry_raw!r}"
        ) from e
    except ValueError as e:
        raise ValueError(
            f"{what} returned malformed structure after one retry: {retry_raw!r}"
        ) from e
