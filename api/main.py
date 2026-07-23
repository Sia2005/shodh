"""
FastAPI entrypoint. Single endpoint that runs the full agent loop and
streams state updates via SSE so the Streamlit UI (or curl) can watch
the plan/search/critique unfold live.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import critic, executor, planner, synthesizer
from agent.state import AgentState, BudgetExceeded, Phase
from retrieval.ranker import dedupe, rerank_by_distance
from retrieval.store import VectorStore

app = FastAPI(title="Shodh — Autonomous Research Agent")


class ResearchRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def run_agent(question: str):
    """Generator that yields SSE-formatted JSON state snapshots as the
    agent progresses. This is the whole orchestration — planner ->
    executor -> synthesizer -> critic -> (loop or done)."""
    state = AgentState(question=question)
    store = VectorStore(collection_name=f"run_{abs(hash(question))}")

    def emit(note: str = ""):
        payload = state.as_dict()
        if note:
            payload["note"] = note
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # PLANNING
        state.sub_questions = planner.plan(question)
        state.advance(Phase.SEARCHING, f"planned {len(state.sub_questions)} sub-questions")
        yield emit("planning complete")

        pending = list(state.sub_questions)
        while True:
            state.tick()
            for sq in pending:
                executor.run_sub_question(sq, state, store)
                yield emit(f"searched: {sq}")
            pending = []

            # SYNTHESIZING
            state.advance(Phase.SYNTHESIZING, "building draft report")
            raw_chunks = store.query(question, n_results=15)
            evidence = rerank_by_distance(dedupe(raw_chunks))
            result = synthesizer.synthesize(question, evidence)
            state.report = result["report"]
            state.claims = result.get("contradictions", [])
            yield emit("draft synthesized")

            # CRITIQUING
            state.advance(Phase.CRITIQUING, "grading draft")
            evidence_summary = "\n".join(f"- {e['title']} ({e['url']})" for e in state.evidence)
            verdict = critic.critique(state.report, evidence_summary)
            yield emit("critique complete")

            if verdict["passes"]:
                state.advance(Phase.DONE, "critic approved")
                yield emit("done")
                return

            # Route back to SEARCHING with targeted gap queries
            state.gaps = verdict["gaps"]
            state.critique_notes.append(json.dumps(verdict))
            pending = state.gaps or [question]  # fallback: retry the main question
            state.advance(Phase.SEARCHING, f"re-searching {len(pending)} gaps")
            yield emit("re-search triggered")

    except BudgetExceeded as e:
        yield emit(f"stopped: {e}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the stream
        state.trace.append(f"[ERROR] {e}")
        yield emit(f"error: {e}")


@app.post("/research")
def research(req: ResearchRequest):
    return StreamingResponse(run_agent(req.question), media_type="text/event-stream")
