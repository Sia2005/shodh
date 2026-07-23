# Shodh — Autonomous Research Agent

## What this is
An agent that plans multi-step research, retrieves and cross-examines web
sources, and produces citation-grounded reports. Includes a self-critique
loop and an eval harness comparing it against single-pass RAG.

## Hard constraints
- Python 3.12, FastAPI, Gemini, Tavily, Chroma, Streamlit.
- NO agent frameworks. Do not add or suggest LangChain, LlamaIndex,
  CrewAI, AutoGen, or Haystack. The agent loop is hand-written.
- Single model provider (Gemini). No multi-provider abstraction layers.
- No auth, no user accounts, no chat history, no PDF ingestion.

## Ownership rules
- Files in agent/ and evals/metrics.py are author-written. Do NOT rewrite
  them unless explicitly asked. Review, critique, and explain instead.
- api/, ui/, retrieval/store.py, tests/ are open for you to implement.

## Conventions
- Type hints on every function signature. Pydantic models for agent state.
- Async throughout the tool layer (httpx, not requests).
- No bare except. Log and re-raise or handle explicitly.
- Every tool call must be bounded: timeout + max retries.

## Commands
- Run API: uvicorn api.main:app --reload
- Run UI: streamlit run ui/app.py
- Tests: pytest
- Evals: python -m evals.run_evals

## Style of help I want
Explain design tradeoffs before writing code. When I ask "why", answer
with reasoning, not a rewrite. I'm newer to Python than JS — flag Python
idioms I should know rather than silently using them.