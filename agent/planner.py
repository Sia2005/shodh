"""
Planner: question -> ordered list of sub-questions.

Calls Gemini once with a strict JSON-only instruction. Kept as a single
LLM call (not a loop) — planning is cheap, execution is where the
budget goes.
"""

from __future__ import annotations

import json

import google.generativeai as genai

from agent import config

config.validate()

_PLANNER_SYSTEM_PROMPT = """You are a research planner. Given a research question, \
break it into 2-5 focused, independently-searchable sub-questions that together \
cover what's needed to answer the original question thoroughly.

Respond ONLY with a JSON array of strings. No preamble, no markdown fences, \
no explanation. Example:
["What is X's current market share?", "How has X's pricing changed since 2024?"]
"""

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            system_instruction=_PLANNER_SYSTEM_PROMPT,
        )
    return _model


def plan(question: str) -> list[str]:
    model = _get_model()
    response = model.generate_content(question)
    raw = response.text.strip()

    # Defensive cleanup in case the model wraps output in fences anyway.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw

    try:
        sub_questions = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner did not return valid JSON: {raw!r}") from e

    if not isinstance(sub_questions, list) or not all(isinstance(q, str) for q in sub_questions):
        raise ValueError(f"Planner returned malformed structure: {sub_questions!r}")

    return sub_questions
