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
numbered list of claims (each with the evidence numbers it cites) and the full text \
of that numbered evidence. Grade EACH claim independently against ONLY the evidence \
at its cited numbers:

- "supported": the cited evidence clearly backs the claim as stated.
- "weakly-supported": the cited evidence is related but doesn't fully back the claim \
  as stated (overreaching, missing nuance, only partially confirmed).
- "unsupported": the cited evidence doesn't back the claim, or the citation is wrong.

Respond ONLY with JSON, no markdown fences:
{
  "claim_verdicts": [
    {"id": "c1", "verdict": "supported" | "weakly-supported" | "unsupported", "reason": "one line"}
  ]
}

Include exactly one verdict per claim you were given, in the same order.
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


def critique(claims: list[dict], evidence: list[dict]) -> dict:
    """claims: synthesizer output, each {"id", "text", "citations", "sub_question"}.
    evidence: the SAME numbered list passed to synthesizer.synthesize(), so a
    claim's "citations" indices mean the same source here as they did there."""
    if not claims:
        # Nothing to grade — and nothing to silently pass either.
        return {"claim_verdicts": []}

    numbered_evidence = "\n\n".join(
        f"[{i + 1}] (source: {e['url']})\n{e['text']}" for i, e in enumerate(evidence)
    )
    claims_block = "\n\n".join(
        f"{c['id']}: {c['text']}\ncited evidence: {c['citations']}" for c in claims
    )
    prompt = f"CLAIMS:\n{claims_block}\n\nEVIDENCE:\n{numbered_evidence}"

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

    result.setdefault("claim_verdicts", [])
    return result


def overall_passes(claim_verdicts: list[dict], max_weak: int = config.MAX_WEAK_CLAIMS) -> bool:
    """No claims to grade is a fail, not a pass — this is the guard against
    silently approving an empty draft, and it holds regardless of caller."""
    if not claim_verdicts:
        return False
    unsupported = sum(1 for v in claim_verdicts if v["verdict"] == "unsupported")
    weak = sum(1 for v in claim_verdicts if v["verdict"] == "weakly-supported")
    return unsupported == 0 and weak <= max_weak
