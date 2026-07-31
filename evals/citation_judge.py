"""
Model-graded citation-support judge.

evals/metrics.py::citation_accuracy (author-owned, unchanged) only checks
that a [n] citation marker points to an index that exists in the source
list -- structural validity, not semantic support. This module adds the
check the eval brief actually asked for: does the evidence cited at [n]
actually back the sentence citing it?

Deliberately NOT built on agent/critic.py. The agent loop re-searches until
it satisfies its own critic (that's the CRITIQUING -> SEARCHING loop in
agent/state.py), so grading the agent with its own critic would bias the
comparison in the agent's favor -- and the baseline has no critic at all.
This is a separate, uniform judge applied the same way to both reports
after the fact, so the comparison stays apples-to-apples. See
evals/README.md for the full reasoning.
"""

from __future__ import annotations

import re

import google.generativeai as genai

from agent import config, json_utils

config.validate()

# Matches a whole [...] bracket's contents so both citation styles the
# synthesizer actually produces are caught: "[3]" and "[2, 4]" (observed in
# practice -- the synthesizer's prompt only shows the single-number form,
# but doesn't always follow it). evals/metrics.py::citation_accuracy uses a
# bare \[(\d+)\] and misses the comma-grouped form; that's a known
# undercount there (protected file, not fixed) -- not repeated here.
_CITATION_BRACKET_RE = re.compile(r"\[([\d,\s]+)\]")
_DIGITS_RE = re.compile(r"\d+")

# Good enough for report prose (splits after ./!/? on a following capital,
# opening paren, or bracket) -- doesn't need to be a real sentence tokenizer.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


def _citation_numbers(text: str) -> list[int]:
    numbers = []
    for bracket in _CITATION_BRACKET_RE.findall(text):
        numbers.extend(int(n) for n in _DIGITS_RE.findall(bracket))
    return numbers

_JUDGE_SYSTEM_PROMPT = """You are auditing a research report's citations. You will \
receive a numbered list of sentences, each paired with the full text of the \
evidence at the source numbers it cited, and nothing else. For each sentence, \
decide whether the cited evidence actually supports it -- not whether the \
sentence sounds plausible, only whether THIS evidence backs it.

Respond ONLY with JSON, no markdown fences:
{
  "verdicts": [
    {"id": 1, "supported": true}
  ]
}

Include exactly one verdict per sentence you were given, in the same order.
"""

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            system_instruction=_JUDGE_SYSTEM_PROMPT,
        )
    return _model


def extract_cited_sentences(report: str) -> list[tuple[str, list[int]]]:
    """Splits a report into sentences and pairs each one carrying at least
    one [n] marker with the (1-indexed) citation numbers it references.
    Sentences with no citation are dropped -- there's nothing to grade."""
    sentences = _SENTENCE_SPLIT_RE.split(report.strip())
    out = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        numbers = _citation_numbers(sentence)
        if numbers:
            out.append((sentence, numbers))
    return out


def citation_support_accuracy(
    report: str, evidence: list[dict], timeout: float = 30.0
) -> tuple[float, int, int]:
    """Returns (score, n_supported_citations, n_total_citations).

    n_total_citations counts individual [n] occurrences -- the same unit
    metrics.citation_accuracy uses, so the two numbers are directly
    comparable. Every citation number in a sentence gets that sentence's
    verdict, since the sentence is graded against the UNION of its cited
    evidence (mirroring how agent/critic.py grades claims), not each
    source individually.

    Score is 0.0 if the report has no citations at all, matching
    metrics.citation_accuracy's convention for that case."""
    cited_sentences = extract_cited_sentences(report)
    n_total = sum(len(numbers) for _, numbers in cited_sentences)
    if n_total == 0:
        return 0.0, 0, 0

    blocks = []
    for i, (sentence, numbers) in enumerate(cited_sentences, start=1):
        evidence_text = "\n---\n".join(
            evidence[n - 1]["text"] for n in numbers if 1 <= n <= len(evidence)
        )
        if not evidence_text:
            # Every cited number is out of range -- nothing to support it with.
            evidence_text = "(no evidence at the cited number(s) -- out of range)"
        blocks.append(f"SENTENCE {i}: {sentence}\nCITED EVIDENCE:\n{evidence_text}")
    prompt = "\n\n".join(blocks)

    # Same one-retry JSON handling the agent's own Gemini calls use: a judge
    # that throws on malformed output would score the report 0.0, which is
    # indistinguishable from "every citation was unsupported" and would
    # quietly corrupt the comparison.
    result = json_utils.generate_json(
        _get_model(), prompt, what="Citation judge", timeout=timeout
    )

    verdicts = {v["id"]: v["supported"] for v in result.get("verdicts", [])}

    n_supported = 0
    for i, (_, numbers) in enumerate(cited_sentences, start=1):
        if verdicts.get(i, False):
            n_supported += len(numbers)

    return n_supported / n_total, n_supported, n_total
