"""
Planner: question -> ordered list of sub-questions.

Calls Gemini once with a strict JSON-only instruction. Kept as a single
LLM call (not a loop) — planning is cheap, execution is where the
budget goes.
"""

from __future__ import annotations

import google.generativeai as genai

from agent import config, json_utils

config.validate()

_PLANNER_SYSTEM_PROMPT = """You are a research planner. Given a research question, \
break it into 2-5 focused, independently-searchable sub-questions that together \
cover what's needed to answer the original question thoroughly.

Respond in English only, regardless of the language of the question.

Respond ONLY with a JSON array of strings. Every element must be a \
double-quoted string. No preamble, no markdown fences, no explanation, no \
nesting. Example:
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


def _validate(sub_questions: object) -> list[str]:
    """Repair-or-reject callback for generate_json. The observed [[...]]
    nesting is fixable without another API call, so flatten one level;
    anything else malformed raises, which triggers the single retry."""
    if isinstance(sub_questions, list) and sub_questions and all(
        isinstance(q, list) for q in sub_questions
    ):
        sub_questions = [q for inner in sub_questions for q in inner]
    if not isinstance(sub_questions, list) or not all(isinstance(q, str) for q in sub_questions):
        raise ValueError(f"Planner returned malformed structure: {sub_questions!r}")
    return sub_questions


def plan(question: str) -> list[str]:
    sub_questions = json_utils.generate_json(
        _get_model(), question, what="Planner", validate=_validate
    )
    return sub_questions
