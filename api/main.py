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

        pending = [{"sub_question": sq, "search_query": sq} for sq in state.sub_questions]
        while True:
            state.tick()
            for task in pending:
                executor.run_sub_question(
                    task["sub_question"], state, store, search_query=task["search_query"]
                )
                yield emit(f"searched: {task['search_query']}")
            pending = []

            # SYNTHESIZING
            state.advance(Phase.SYNTHESIZING, "building draft report")
            raw_chunks = store.query(question, n_results=15)
            evidence = rerank_by_distance(dedupe(raw_chunks))
            # Charge here, not at fetch time: this is the text that actually
            # enters a Gemini prompt (~4 chars/token, same heuristic executor.py
            # used to apply too early, before retrieval had even happened).
            state.spend(sum(len(e.get("text", "")) for e in evidence) // 4)
            result = synthesizer.synthesize(question, state.sub_questions, evidence)
            state.report = result["report"]
            state.claims = result["claims"]
            state.contradictions = result.get("contradictions", [])
            yield emit("draft synthesized")

            # Guard: no claims means nothing was verifiably extracted from the
            # evidence — this is a hard failure, not a retry-with-gaps case
            # (there's no claim text to build a gap from).
            if not state.claims:
                state.advance(Phase.FAILED, "synthesizer produced zero claims")
                yield emit("failed: no claims extracted")
                return

            # CRITIQUING
            state.advance(Phase.CRITIQUING, "grading draft")
            state.spend(sum(len(e.get("text", "")) for e in evidence) // 4)
            verdict = critic.critique(state.claims, evidence)
            state.claim_verdicts = verdict["claim_verdicts"]
            yield emit("critique complete")

            if critic.overall_passes(state.claim_verdicts):
                state.advance(Phase.DONE, "critic approved")
                yield emit("done")
                return

            # Route back to SEARCHING with targeted gap queries — each failed
            # claim's own text becomes the next search query.
            claims_by_id = {c["id"]: c for c in state.claims}
            failed = [v for v in state.claim_verdicts if v["verdict"] != "supported"]
            state.gaps = [
                {
                    "claim": claims_by_id[v["id"]]["text"],
                    "sub_question": claims_by_id[v["id"]]["sub_question"],
                }
                for v in failed
            ]
            state.critique_notes.append(json.dumps(verdict))
            pending = [{"sub_question": g["sub_question"], "search_query": g["claim"]} for g in state.gaps]
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
