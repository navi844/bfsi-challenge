"""FastAPI backend for the BFSI Agent Observability Challenge starter kit.

READ THIS BEFORE YOU START: this app already works correctly end to end.
It answers real customer questions, correctly picks one or more of three
tools per question, and correctly delegates fraud-referral decisions to a
separate sub-agent. What it does NOT have is any observability at all -
no spans, no traces, no cost tracking - and no guard against a crafted
message overriding its own instructions. Those gaps are the whole exercise.
See the outline document's Section 2 for the full list, and Section 3 for
the step-by-step plan to close each one using OpenTelemetry and Jaeger.
"""
import json

from fastapi import FastAPI, Query

from llm_provider import chat_raw
from tools import TOOL_SPECS, TOOL_FUNCTIONS
from delegation import delegate_to_fraud_check
from memory_store import store
from otel_setup import setup_tracing
from opentelemetry import trace

tracer = setup_tracing(service_name="bfsi-assistant")

app = FastAPI(title="BFSI Virtual Assistant - Starter Kit (no observability yet)")

SYSTEM_PROMPT = (
    "You are a customer service assistant for Lloyds Financial (a training scenario). "
    "For ANY question about rates, limits, eligibility, fraud handling, complaints, or "
    "savings products, you MUST call lookup_policy before writing your answer - this "
    "applies even if the question sounds like it needs account-specific data. Use "
    "calculate_monthly_repayment for repayment arithmetic, and check_account_balance for "
    "a customer's current balance or account type. A single question may need more than "
    "one tool - call every tool you actually need before answering. Keep answers short."
)
MAX_AGENT_STEPS = 6


def _run_agent_turn(question: str, history: list = None) -> dict:
    """The main agent loop. No span, no trace_id, no cost - just the loop
    itself. Compare this function to the one you'll have after Step 2:
    same logic, wrapped in a root span that makes every one of these
    requests findable afterward instead of only visible while it runs."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend({"role": t["role"], "content": t["content"]} for t in history)
    messages.append({"role": "user", "content": question})

    tool_sequence = []
    steps = 0
    final_answer = None
    for steps in range(1, MAX_AGENT_STEPS + 1):
        # Prompt-injection guard: simple keyword/pattern check before model call.
        try:
            active_span = trace.get_current_span()
            combined_text = "\n".join(
                [m.get("content", "") for m in messages if isinstance(m, dict)]
            ).lower()
            injection_patterns = [
                "ignore previous instructions",
                "disregard the system prompt",
                "you are now",
                "approve without checking",
            ]
            for pat in injection_patterns:
                if pat in combined_text:
                    if active_span is not None:
                        try:
                            active_span.set_attribute("bfsi.guardrail.triggered", True)
                            active_span.set_attribute("bfsi.guardrail.reason", pat)
                        except Exception:
                            pass
                    break
        except Exception:
            pass
        turn = chat_raw(messages=messages, tools=TOOL_SPECS)
        if not turn.tool_calls:
            final_answer = turn.content
            break
        messages.append({"role": "assistant", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in turn.tool_calls]})
        for tc in turn.tool_calls:
            tool_sequence.append(tc.name)
            args = json.loads(tc.arguments or "{}")
            fn = TOOL_FUNCTIONS[tc.name]
            result = fn(**args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return {"answer": final_answer, "steps": steps, "tool_sequence": tool_sequence}


@app.get("/")
def root():
    return {"service": "bfsi-assistant-starter", "docs": "/docs",
            "note": "no tracing, no cost tracking, no prompt-injection guard yet - that's the exercise"}


@app.get("/ask")
def ask(q: str = Query(...)):
    with tracer.start_as_current_span("agent_turn") as span:
        span.set_attribute("agent.question", (q or "")[:200])
        result = _run_agent_turn(q)
        span.set_attribute("agent.steps", result.get("steps", 0))
        span.set_attribute("agent.tool_sequence", ",".join(result.get("tool_sequence", [])))
        return result


@app.post("/chat")
def chat(session_id: str = Query(...), message: str = Query(...)):
    session = store.get_or_create(session_id)
    history = [{"role": t["role"], "content": t["content"]} for t in session.turns]
    session.append("user", message)
    result = _run_agent_turn(message, history=history)
    session.append("assistant", result["answer"] or "")
    session.truncate()
    return {"session_id": session_id, "answer": result["answer"]}


@app.get("/memory/{session_id}")
def memory(session_id: str):
    return store.inspect(session_id)


@app.post("/memory/{session_id}/reset")
def memory_reset(session_id: str):
    store.reset(session_id)
    return {"session_id": session_id, "reset": True}


@app.get("/delegate")
def delegate(amount: float = Query(9500.0)):
    return delegate_to_fraud_check(amount)
