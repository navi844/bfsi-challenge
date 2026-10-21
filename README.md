# BFSI Virtual Assistant — Starter Kit

*This is the "before" state. Read the companion document,
**BFSI_Observability_Challenge_Outline.docx**, before writing any code -
it shows you the complete target architecture first, names every gap in
this repo on purpose, and gives you a step-by-step plan (with suggested
GitHub Copilot prompts) to close each one.*

## What this is

A working Lloyds Financial (training scenario) customer-service agent. It
answers real questions, correctly calls one or more of three tools per
question, and correctly delegates fraud-referral decisions to a separate
sub-agent. Run it right now and it works end to end.

## What this is NOT (yet)

It has **zero observability** and **one deliberate security gap**:

- No tracing of any kind - not a single span, not a request ID in the logs.
- No visibility into WHICH tool fired on a multi-tool question, or how long
  each one took.
- The fraud-referral sub-agent's own reasoning loop is completely invisible
  from outside - a runaway loop in there would look, from the outside,
  identical to a normal slow request.
- Every OpenAI response already contains real token-usage numbers
  (`response.usage`) - this codebase reads them and throws them away. There
  is currently no way to answer "what did this conversation cost us."
- No guard against prompt injection. Run `python agent.py` and look at
  `run_injection_demo()`'s output for yourself.
- No `docker-compose.yml`, no OpenTelemetry Collector config, no Jaeger.
  You stand up that whole pipeline yourself in Step 1.

**This exercise uses OpenTelemetry and Jaeger only** - no Prometheus, no
Grafana, no managed backend. OpenTelemetry's SDK exports traces over OTLP;
the OTel Collector (itself part of the OpenTelemetry project, not a
third-party tool) batches and forwards them to Jaeger, which is where
you'll do all your actual debugging.

## Setup

1. `cp .env.example .env` and fill in `OPENAI_API_KEY`.
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python make_documents.py`
5. `python build_vectorstore.py`
6. **Terminal 1:** `uvicorn app:app --reload --port 8000`
7. **Terminal 2:** `python agent.py`

You should see correct answers, a correct fraud-referral verdict, and the
injection-demo output - all with nothing in Jaeger, because Jaeger doesn't
exist yet. That's the starting line.

## Where to go next

Open **BFSI_Observability_Challenge_Outline.docx**. Section 1 shows the
complete target architecture. Section 3 is the step-by-step build plan,
Step 1 onward, each with a suggested Copilot prompt. Nothing in this repo
should surprise you if you've read Section 2 first - every gap listed
there is really here, and nothing else is missing beyond what's listed.

## File map (none of these have any tracing yet - that's for you to add)

| File | What it does |
|---|---|
| `app.py` | FastAPI app - `/ask`, `/chat`, `/memory/{id}`, `/delegate`. The main agent loop lives in `_run_agent_turn()`. |
| `llm_provider.py` | OpenAI chat wrapper. Token usage is read from the response and discarded - see Step 5. |
| `tools.py` | The three tools: `lookup_policy` (RAG), `calculate_monthly_repayment`, `check_account_balance` (mock). |
| `delegation.py` | The fraud-referral sub-agent - its own independent reasoning loop, called from `/delegate`. |
| `memory_store.py` | In-memory session store backing `/chat`. |
| `vectorstore.py`, `loaders.py`, `pii.py`, `chunking.py`, `context.py` | Document ingestion pipeline - PII-redacted, chunked, embedded into Chroma. Unrelated to the observability exercise; left as-is. |
| `make_documents.py`, `build_vectorstore.py` | Run once, in order, to generate and embed the five source documents. |
| `agent.py` | Terminal demo client, including the prompt-injection example. |
