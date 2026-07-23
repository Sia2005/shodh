"""
Critic: grades the draft report claim-by-claim against retrieved evidence.
Weak or uncited claims become targeted re-search queries fed back into
the executor. This is the differentiator loop — see state.py Phase
transitions for how CRITIQUING can route back to SEARCHING.
"""

from __future__ import annotations

import json

import google.generativeai as genai

from agent import config

config.validate()

_CRITIC_SYSTEM_PROMPT = """You are a strict fact-checking critic. You will receive a \
draft research report and the evidence it was built from. Check every claim:

1. Is it actually supported by the cited evidence, or is it unsupported / overreaching?
2. Are there important sub-questions the report doesn't adequately answer?

Respond ONLY with JSON, no markdown fences:
{
  "passes": true | false,
  "weak_claims": ["claim text that is unsupported or overreaching", ...],
  "gaps": ["follow-up search query to close an evidence gap", ...]
}

Set "passes" to true only if weak_claims and gaps are both empty.
"""

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            system_instruction=_CRITIC_SYSTEM_PROMPT,
        )
    return _model


def critique(report: str, evidence_summary: str) -> dict:
    prompt = f"DRAFT REPORT:\n{report}\n\nEVIDENCE USED:\n{evidence_summary}"
    model = _get_model()
    response = model.generate_content(prompt)
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Critic did not return valid JSON: {raw!r}") from e

    result.setdefault("weak_claims", [])
    result.setdefault("gaps", [])
    result.setdefault("passes", not result["weak_claims"] and not result["gaps"])
    return result
