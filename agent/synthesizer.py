"""
Synthesizer: retrieved evidence -> structured report with inline numbered
citations, and contradiction detection between disagreeing sources.
"""

from __future__ import annotations

import json

import google.generativeai as genai

from agent import config

config.validate()

_SYNTH_SYSTEM_PROMPT = """You are a research synthesizer. You will receive a research \
question and a numbered list of evidence excerpts, each tagged with a source URL.

Write a report that answers the question using ONLY the provided evidence. \
Every factual claim must end with a bracketed citation number referring to the \
evidence list, e.g. [3]. If two pieces of evidence disagree on a claim, do not \
silently pick one — state the disagreement explicitly and cite both sides.

Respond ONLY with JSON in this shape, no markdown fences:
{
  "report": "full report text with inline [n] citations",
  "contradictions": [
    {"claim": "...", "source_a": n, "source_b": n, "note": "how they disagree"}
  ]
}
"""

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            system_instruction=_SYNTH_SYSTEM_PROMPT,
        )
    return _model


def synthesize(question: str, evidence_chunks: list[dict]) -> dict:
    """evidence_chunks: list of {"text": str, "url": str, "title": str}"""
    numbered = "\n\n".join(
        f"[{i+1}] (source: {c['url']})\n{c['text']}" for i, c in enumerate(evidence_chunks)
    )
    prompt = f"QUESTION: {question}\n\nEVIDENCE:\n{numbered}"

    model = _get_model()
    response = model.generate_content(prompt)
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Synthesizer did not return valid JSON: {raw!r}") from e

    result.setdefault("contradictions", [])
    return result
