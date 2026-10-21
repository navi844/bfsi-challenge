"""A delegated 'sub-agent' - the fraud-referral checker - that the main
agent calls into for one specific kind of question: whether a transaction
amount needs to be referred to the Fraud Operations queue. It runs its own
independent reasoning loop, with its own tool calls, completely separate
from the main agent's loop in app.py.

THIS FILE HAS NO OBSERVABILITY OF ANY KIND. Right now, if you call
/delegate, the whole thing just... happens, with no visible structure
beyond print statements you might add yourself while debugging. Once
there's a tracer (Step 1), wrapping this function's body in its own span
is Step 4 of the outline - and the part that actually matters there isn't
creating a span, it's making sure that span ends up NESTED inside whatever
span was active when delegate_to_fraud_check() was called, not as a second,
unrelated root span. Get the nesting right and a trace shows the real shape
of this system: one agent delegating to a specialist, not two agents that
happen to have run near each other in time."""
from llm_provider import chat_raw
from tools import TOOL_SPECS, TOOL_FUNCTIONS
from otel_setup import setup_tracing
import json

tracer = setup_tracing(service_name="bfsi-assistant")

SUB_AGENT_MAX_STEPS = 4

FRAUD_SUB_AGENT_SYSTEM_PROMPT = (
    "You are the Fraud Referral Sub-Agent for Lloyds Financial (training scenario). "
    "You are delegated a single transaction amount and must decide, using lookup_policy "
    "to confirm the current threshold, whether it must be referred to the Fraud Operations "
    "queue. Answer with just 'REFER' or 'CLEAR' and one short sentence why."
)


def delegate_to_fraud_check(transaction_amount: float) -> dict:
    """Called BY the main agent - see app.py's /delegate endpoint. Runs its
    own tool-calling loop, independent of whatever loop (if any) called it."""
    with tracer.start_as_current_span("sub_agent_turn") as span:
        span.set_attribute("agent.delegation.amount", float(transaction_amount))
        messages = [
            {"role": "system", "content": FRAUD_SUB_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Transaction amount: GBP {transaction_amount:.2f}. Should this be referred?"},
        ]
        verdict_text = None
        sub_steps = 0
        for sub_steps in range(1, SUB_AGENT_MAX_STEPS + 1):
            turn = chat_raw(messages=messages, tools=TOOL_SPECS)
            if not turn.tool_calls:
                verdict_text = turn.content
                break
            messages.append({"role": "assistant", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in turn.tool_calls]})
            for tc in turn.tool_calls:
                args = json.loads(tc.arguments or "{}")
                fn = TOOL_FUNCTIONS[tc.name]
                result = fn(**args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

        verdict = "REFER" if verdict_text and "REFER" in verdict_text.upper() else \
            ("UNRESOLVED" if verdict_text is None else "CLEAR")
        span.set_attribute("agent.delegation.sub_steps", sub_steps)
        return {"verdict": verdict, "detail": verdict_text, "sub_steps": sub_steps}
