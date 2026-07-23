"""
Agent state machine + context budget management.

Interviewers will ask: "how do you stop the agent from looping forever
or blowing the context window?" This module is the answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from agent.config import MAX_ITERATIONS, MAX_TOKENS


class Phase(Enum):
    PLANNING = auto()
    SEARCHING = auto()
    SYNTHESIZING = auto()
    CRITIQUING = auto()
    DONE = auto()
    FAILED = auto()


# Legal transitions. Anything not listed here is rejected by advance().
_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.PLANNING: {Phase.SEARCHING, Phase.FAILED},
    Phase.SEARCHING: {Phase.SYNTHESIZING, Phase.FAILED},
    Phase.SYNTHESIZING: {Phase.CRITIQUING, Phase.FAILED},
    # Critic can send us back to SEARCHING for targeted re-retrieval,
    # or forward to DONE if the draft passes.
    Phase.CRITIQUING: {Phase.SEARCHING, Phase.DONE, Phase.FAILED},
    Phase.DONE: set(),
    Phase.FAILED: set(),
}


class BudgetExceeded(Exception):
    """Raised when the agent hits an iteration or token ceiling."""


@dataclass
class AgentState:
    question: str
    phase: Phase = Phase.PLANNING

    # --- guards against runaway loops ---
    max_iterations: int = MAX_ITERATIONS
    max_tokens: int = MAX_TOKENS
    iteration_count: int = 0
    tokens_used: int = 0

    # --- working memory ---
    sub_questions: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)  # retrieved chunks + source
    claims: list[dict[str, Any]] = field(default_factory=list)    # extracted claims + citations
    critique_notes: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)  # sub-questions flagged for re-search
    report: str | None = None

    trace: list[str] = field(default_factory=list)  # human-readable log for the UI stream

    def advance(self, next_phase: Phase, note: str = "") -> None:
        if next_phase not in _TRANSITIONS[self.phase]:
            raise ValueError(f"Illegal transition: {self.phase} -> {next_phase}")
        self.trace.append(f"[{self.phase.name} -> {next_phase.name}] {note}")
        self.phase = next_phase

    def spend(self, tokens: int) -> None:
        self.tokens_used += tokens
        if self.tokens_used > self.max_tokens:
            self.advance(Phase.FAILED, "token budget exceeded")
            raise BudgetExceeded(f"tokens_used={self.tokens_used} > max_tokens={self.max_tokens}")

    def tick(self) -> None:
        """Call once per critique->search loop iteration."""
        self.iteration_count += 1
        if self.iteration_count > self.max_iterations:
            self.advance(Phase.FAILED, "max iterations exceeded")
            raise BudgetExceeded(f"iteration_count={self.iteration_count} > max_iterations={self.max_iterations}")

    def as_dict(self) -> dict[str, Any]:
        """For SSE streaming to the UI."""
        return {
            "phase": self.phase.name,
            "iteration": self.iteration_count,
            "tokens_used": self.tokens_used,
            "sub_questions": self.sub_questions,
            "n_evidence": len(self.evidence),
            "n_claims": len(self.claims),
            "gaps": self.gaps,
            "trace": self.trace[-10:],  # last 10 events only
        }
