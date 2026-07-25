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
question, the sub-questions it was decomposed into, and a numbered list of evidence \
excerpts, each tagged with a source URL.

Work in two stages:

STAGE 1 — Extract claims. Identify every atomic factual assertion the evidence \
actually supports. For each claim, give: the claim stated as one self-contained \
sentence ("text"), the evidence numbers that support it ("citations", 1-indexed, \
matching the numbered evidence list), and which sub-question it most directly \
answers ("sub_question" — must be exactly one of the sub-questions listed below). \
Only include a claim if at least one evidence excerpt actually supports it — do not \
invent claims the evidence doesn't contain.

STAGE 2 — Write the report FROM the claims above. Every sentence in the report must \
correspond to one or more of the claims from stage 1, and must cite the SAME \
evidence numbers that claim's "citations" lists, e.g. [3]. Do not introduce a fact \
in the report that isn't backed by a stage-1 claim.

If two claims conflict on the same fact, do not silently pick one — record it under \
"contradictions" instead, citing both sides.

Respond ONLY with JSON in this exact shape, no markdown fences:
{
  "claims": [
    {"text": "...", "citations": [1, 3], "sub_question": "..."}
  ],
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


def synthesize(question: str, sub_questions: list[str], evidence_chunks: list[dict]) -> dict:
    """evidence_chunks: list of {"text": str, "url": str, "title": str}"""
    numbered = "\n\n".join(
        f"[{i+1}] (source: {c['url']})\n{c['text']}" for i, c in enumerate(evidence_chunks)
    )
    sub_questions_list = "\n".join(f"- {sq}" for sq in sub_questions)
    prompt = f"QUESTION: {question}\n\nSUB-QUESTIONS:\n{sub_questions_list}\n\nEVIDENCE:\n{numbered}"

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
    # Assign stable ids ourselves rather than trusting the model to keep
    # them unique/sequential — it only needs to get content right.
    for i, claim in enumerate(result.setdefault("claims", []), start=1):
        claim["id"] = f"c{i}"
    return result
